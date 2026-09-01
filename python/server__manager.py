import ast
import shutil
import socket
import subprocess
import textwrap
from os import environ
from pathlib import Path
from string import Template
from typing import IO

import extract_ports
from shared__util import (
    AckMessage,
    BadHeader,
    BuildLiveCommand,
    ErrorMessage,
    NamedFile,
    NormalTermination,
    StartLiveCommand,
    UnexpectedTermination,
    WaveformSimCommand,
    big_receive,
    deserialize_dataclass,
    first_matching,
    header_to_dc,
    send_message,
    serialize_dataclass,
)

msg_dict = dict[str, int]

def deserialize_dict(d: str) -> msg_dict:
    return ast.literal_eval(d)

executable_path = Path("./obj_dir/Vtop")
backup_executable_path = Path("./executable_backup")

def live_sim(sock: socket.socket):
    global executable_path
    if not executable_path.is_file():
        sock.send(ErrorMessage.CODE.encode())
        send_message(serialize_dataclass(ErrorMessage("Nothing has been compiled yet. Run build_live_sim first!")), sock)
        return
    else:
        sock.send(AckMessage.CODE.encode())
        send_message(serialize_dataclass(AckMessage()), sock)

    process = subprocess.Popen(executable_path, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    in_pipe: IO[str] = process.stdin # pyright: ignore[reportAssignmentType]
    out_pipe: IO[str] = process.stdout # pyright: ignore[reportAssignmentType]

    while(True):
        inp = big_receive(conn).decode()
        match inp:
            case "exit":
                print("Client requested live sim exit")
                send_message("exit", conn)
                print("Returning to main command loop")
                # kill subprocess. Telling it to terminate then wait() doesn't seem to work?
                process.kill()
                break
            case "": # Received empty: paused
                continue
            case _: # Otherwise input must be dataclass string
                try: # Try to convert; if it fails print error rather than crash
                    input_string = str(deserialize_dict(inp))
                except ValueError as e:
                    send_message(f"Failure with input {inp}: e", conn)
                    continue

        in_pipe.write(input_string + "\n")
        in_pipe.flush()

        verilog_prints: list[str] = []
        system_update_string: str = ""

        while True:
            # receive strings until we get a system string
            # we know system string is last because model eval is what triggers
            # display prints and is called before sending state
            output_string = out_pipe.readline().strip()
            if output_string.startswith("secretkey"):
                system_update_string = output_string[len("secretkey"):]
                break
            else:
                if not i_am_a_docker:
                    m = textwrap.indent(output_string, " " * 4)
                    print(m)
                verilog_prints.append(output_string)

        send_message(repr(verilog_prints), sock)
        send_message(system_update_string, sock)
    # TODO: properly close process. Writing "exit\n" and calling process.wait() hangs forever...

def verify_ports(candidate_input: dict[str, int], candidate_output: dict[str, int], canonical_input: dict[str, int], canonical_output: dict[str, int]):
    i_extra_ports: dict[str, int] = {}
    i_wrong_length_ports: dict[str, int] = {}
    i_missing_ports: dict[str, int] = {}
    
    o_extra_ports: dict[str, int] = {}
    o_wrong_length_ports: dict[str, int] = {}
    o_missing_ports: dict[str, int] = {}

    dicts = [i_extra_ports, i_wrong_length_ports, i_missing_ports, o_extra_ports, o_wrong_length_ports, o_missing_ports]

    for port, width in candidate_input.items():
        if not port in canonical_input:
            i_extra_ports[port] = width
        elif width != canonical_input[port]:
            i_wrong_length_ports[port] = width

    for port, width in candidate_output.items():
        if not port in canonical_output:
            o_extra_ports[port] = width
        elif width != canonical_output[port]:
            o_wrong_length_ports[port] = width

    for port, width in canonical_input.items():
        if port not in candidate_input:
            i_missing_ports[port] = width

    for port, width in canonical_output.items():
        if port not in candidate_output:
            o_missing_ports[port] = width

    if any(len(d) > 0 for d in dicts):
        return ErrorMessage(repr(dicts))
    else:
        return AckMessage()

def try_waveform_run(file_type: str, files: list[NamedFile]):
    names = [file.name for file in files]
    try:
        names.remove("tb.v")
    except ValueError:
        return None, ErrorMessage(f"SRVRSEZ:Lacking a tb.v (Client should have caught this)")
    names.insert(0, "tb.v") # put at front to indicate top to Verilator

    # get the tb file to manipulate it (we know it is there)
    tb_file = first_matching(files, lambda x: x.name == "tb.v")

    filename = f"temp.{file_type}"
    output_path = Path(filename)
    # Delete the output file in case a previous run put one there
    output_path.unlink(missing_ok=True)

    if tb_file.content.find("$DUMP_FILENAME") == -1:
        return None, ErrorMessage("SRVRSEZ:Testbench did not include wildcard "
        "$DUMP_FILENAME; should have lines $dumpfile(\"$DUMP_FILENAME\"); "
        "and $dumpvars(0, tb);")
    else:
        tb_file.content = Template(tb_file.content).safe_substitute(DUMP_FILENAME=filename)


    for file in files:
        file.to_disk(Path("./user_inputs"))

    filenames_str = " ".join(names)
    envvars = environ.copy() | {"COMPILE_FILES": filenames_str, "CXXFLAGS": "-fdiagnostics-color"}

    proc = subprocess.run(["/bin/bash", "./Waveform_Run.sh", file_type], stderr=subprocess.PIPE, env=envvars)

    match proc.returncode:
        case 0:
            try:
                output_file = output_path.read_bytes()
            except FileNotFoundError:
                return None, ErrorMessage("SRVRSEZ:Testbench ran successfully but did not "
                f"output to file; should have lines $dumpfile(\"$DUMP_FILENAME\"); and $dumpvars(0, tb);")
            return output_file, AckMessage()
        case _:
            return None, ErrorMessage(f"\n\n{proc.stderr.decode()}")

def waveform_sim(sock: socket.socket, file_type: str, files: list[NamedFile]):
    waveform_bytes, result = try_waveform_run(file_type, files)

    sock.send(result.CODE.encode())
    send_message(serialize_dataclass(result), sock)

    match result:
        case ErrorMessage():
            pass # Already sent error message, nothing more to do
        case AckMessage():
            send_message(waveform_bytes, sock) # pyright: ignore[reportArgumentType]

def build_live(sock: socket.socket, files: list[NamedFile], expected_inputs: dict[str, int], expected_outputs: dict[str, int]):
    # Tries to make Verilog header. If it works, checks ports.
    # Only if that works does it compile — therefore the executable is not
    # overwritten with one for a correct but unusable program

    names = [file.name for file in files]
    try:
        names.remove("top.v")
    except ValueError:
        return ErrorMessage(f"Lacking a top.v. Client should have caught this.")
    names.insert(0, "top.v") # put at front to indicate top to Verilator

    for file in files:
        file.to_disk(Path("./user_inputs"))

    # List is passed in as an environment variable
    # Server passes -I./user_inputs so it can find these files by name
    filenames_str = " ".join(names)
    envvars = environ.copy() | {"COMPILE_FILES": filenames_str, "CXXFLAGS": "-fdiagnostics-color"}

    proc = subprocess.run(["make", "generate_code"], stderr=subprocess.PIPE, env=envvars)

    match proc.returncode:
        case 0:
            # continue to generating exe
            sock.send(AckMessage().CODE.encode())
            send_message(serialize_dataclass(AckMessage()), sock)
        case _:
            e = ErrorMessage(f"\n\n{proc.stderr.decode()}")
            sock.send(e.CODE.encode())
            send_message(serialize_dataclass(e), sock)
            return False
        
    input_ports, output_ports = extract_ports.ports_dicts(Path("./obj_dir/Vtop.h"))

    check = verify_ports(input_ports, output_ports, expected_inputs, expected_outputs)

    match check:

        case AckMessage():
            sock.send(AckMessage().CODE.encode())
            send_message(serialize_dataclass(AckMessage()), sock)
        case ErrorMessage(_):
            sock.send(check.CODE.encode())
            send_message(serialize_dataclass(check), sock)
            return False
        
    extract_ports.write_driver(Path("./simulator_driver_template.cpp"), Path("./simulator_driver_generated.cpp"), input_ports, output_ports)

    proc = subprocess.run(["make", "finish_build"], stderr=subprocess.PIPE, env=envvars)

    match proc.returncode:
        case 0:
            sock.send(AckMessage().CODE.encode())
            send_message(serialize_dataclass(AckMessage()), sock)
            return True
        case _:
            e = ErrorMessage(f"\n\n{proc.stderr.decode()}")
            sock.send(e.CODE.encode())
            send_message(serialize_dataclass(e), sock)
            return False

if __name__ == "__main__":
    i_am_a_docker = "FPGA_DOCKER_SERVER" in environ

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # disable Nagle's algorithm. was a HUGE headache when testing v2
        server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        if i_am_a_docker:
            server_sock.bind(("0.0.0.0", 9834))
            server_sock.listen()
            # Used as "ack" message so client knows the server is ready
            print("Only the computer will ever see this </3")
        else:
            if shutil.which("verilator") is None:
                print("Verilator is not in your terminal path.")
                print("Try running this in a fresh terminal if you just installed Verilator.")
                exit(1)
            server_sock.bind(("0.0.0.0", 0))
            _, port = server_sock.getsockname()
            server_sock.listen()

            print(f"Local server has started and is bound to port {port}")
            print(f"Run the client script, with the port number as its argument, in another window/tab to connect.")

            my_folder = Path(__file__).resolve().parent.parent 
            my_folder.joinpath("./user_inputs").mkdir(exist_ok=True) 

        conn, addr = server_sock.accept()
        server_sock.close() # No more connections
        conn.send("Ack!".encode()) # Clients after close will receive EOF instead

        print("Your local client has connected to this server. Run commands in its terminal and watch output here. Errors will be redirected to the client if they occur.")
        while True:
            # TODO: maybe, instead of fixed-size header codes,
            #   prefix dataclass serializations with type name?
            header = conn.recv(2)
            if header == b'':
                print("Client disconnected normally")
                exit(0)
            dc_type = header_to_dc(header.decode())
            try:
                message = big_receive(conn)
            except UnexpectedTermination:
                print("Client terminated after sending length value, without sending full message")
                exit(1)
            except NormalTermination:
                print("Client disconnected normally")
                exit(0)
            except BadHeader as e:
                print(f"Client sent invalid header {str(e)}")
                exit(1)
            dict_str = message.decode()
            command = deserialize_dataclass(dict_str, dc_type)
            # print(command)

            match command:
                case BuildLiveCommand(files, expected_inputs, expected_outputs):
                    Path("./user_inputs").mkdir(exist_ok=True)
                    build_live(conn, files, expected_inputs, expected_outputs)
                case StartLiveCommand():
                    live_sim(conn)
                case WaveformSimCommand(file_type, files):
                    waveform_sim(conn, file_type, files)
