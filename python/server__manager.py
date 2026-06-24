import ast
import dataclasses as dc
import shutil
import socket
import subprocess
import textwrap
from os import environ
from pathlib import Path
from string import Template
from typing import IO

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
    header_to_dc,
    send_message,
    serialize_dataclass,
)

try:
    from colorama import Fore, Style  # TODO: make it lazy import in the future
    colorama_available = True
except ModuleNotFoundError:
    colorama_available = False

msg_dict = dict[str, int]

def deserialize_dict(d: str) -> msg_dict:
    return ast.literal_eval(d)

executable_path = Path("./obj_dir/Vtop")

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
                    if colorama_available:
                        print(f"{Fore.BLUE}{Style.BRIGHT}{m}{Style.RESET_ALL}")
                    else:
                        print(m)
                verilog_prints.append(output_string)

        send_message(repr(verilog_prints), sock)
        send_message(system_update_string, sock)
    # TODO: properly close process. Writing "exit\n" and calling process.wait() hangs forever...

def try_make(files: list[NamedFile]):
    '''Runs make with the given list of NamedFiles, saving them to
    a folder first. Assumes that the client has checked that there is one
    called top.v.'''

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

    # This and the CXXFLAGS make it so that errors' colors are preserved; the
    #   commands otherwise know they are not in a terminal and strip them
    #   Not sure why the env var is also needed (in real terminal it isn't)
    proc = subprocess.run(["make"], stderr=subprocess.PIPE, env=envvars)

    match proc.returncode:
        case 0:
            return AckMessage()
        case other:
            return ErrorMessage(f"\n\n{proc.stderr.decode()}")
        
def try_waveform_run(name: str, files: list[NamedFile]):
    names = [file.name for file in files]
    try:
        names.remove("tb.v")
    except ValueError:
        return None, ErrorMessage(f"SRVRSEZ:Lacking a tb.v (Client should have caught this)")
    names.insert(0, "tb.v") # put at front to indicate top to Verilator

    for file in files:
        if file.name == "tb.v":
            break
    tb_file = file
    if tb_file.content.find("$DUMP_FILENAME") == -1:
        return None, ErrorMessage("SRVRSEZ:Testbench did not include wildcard "
        "$DUMP_FILENAME; should have lines $dumpfile(\"$DUMP_FILENAME\"); "
        "and $dumpvars(0, tb);")
    else:
        tb_file.content = Template(tb_file.content).safe_substitute(DUMP_FILENAME=name)

    # Delete the output file in case a previous run put one there
    Path(name).unlink(missing_ok=True)

    for file in files:
        file.to_disk(Path("./user_inputs"))

    filenames_str = " ".join(names)
    envvars = environ.copy() | {"COMPILE_FILES": filenames_str, "CXXFLAGS": "-fdiagnostics-color"}
    proc = subprocess.run(["/bin/bash", "./Waveform_Run.sh"], stderr=subprocess.PIPE, env=envvars)

    match proc.returncode:
        case 0:
            try:
                output_file = NamedFile.from_fp(open(name, "r"), close_after=True)
            except FileNotFoundError:
                return None, ErrorMessage("SRVRSEZ:Testbench ran successfully but did not "
                f"output to file {name}; should have lines $dumpfile(\"$DUMP_FILENAME\"); and $dumpvars(0, tb);")
            return output_file, AckMessage()
        case _:
            return None, ErrorMessage(f"\n\n{proc.stderr.decode()}")

def waveform_sim(sock: socket.socket, name: str, files: list[NamedFile]):
    print(f"Name: {name}")
    output_file, result = try_waveform_run(name, files)

    sock.send(result.CODE.encode())
    send_message(serialize_dataclass(result), sock)

    match output_file, result:
        case None, ErrorMessage():
            pass # Already sent error message, nothing more to do
        case NamedFile(), AckMessage():
            send_message(serialize_dataclass(output_file), sock) # pyright: ignore[reportArgumentType]


def build_live(sock: socket.socket, files: list[NamedFile]):
    result = try_make(files)
    sock.send(result.CODE.encode())
    send_message(serialize_dataclass(result), sock)
    if isinstance(result, AckMessage):
        send_message(Path("ports.txt").read_text(), sock)

if __name__ == "__main__":
    i_am_a_docker = "FPGA_DOCKER_SERVER" in environ

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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
                case BuildLiveCommand(files):
                    build_live(conn, files)
                    pass
                case StartLiveCommand():
                    live_sim(conn)
                    pass
                case WaveformSimCommand(name, files):
                    waveform_sim(conn, name, files)
                    pass
