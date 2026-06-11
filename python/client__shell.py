import base64
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from argparse import ArgumentParser
from enum import Enum, auto
from pathlib import Path
from sys import argv
from typing import IO

from client__paths import (
    docker_tag_filepath,
    live_sim_folder,
    settings_filepath,
    testbench_folder,
    top_folder,
    waveforms_folder,
)
from colorama import Fore, Style
from prompt_toolkit import HTML, PromptSession, print_formatted_text, prompt
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    NestedCompleter,
    WordCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.shortcuts import CompleteStyle
from shared__util import (
    AckMessage,
    AnyCommand,
    BuildLiveCommand,
    ErrorMessage,
    NamedFile,
    StartLiveCommand,
    WaveformSimCommand,
    big_receive,
    deserialize_dataclass,
    receive_error_or_ack,
    send_message,
    serialize_dataclass,
)


def error_title():
    return f"{Fore.RED}{Style.BRIGHT}Error:{Style.RESET_ALL}"

def success_title():
    return f"{Fore.GREEN}{Style.BRIGHT}Success:{Style.RESET_ALL}"

def print_parser_error(parser: ArgumentParser, message: str):
    print(parser.format_usage())
    print(message)

def send_command(command: AnyCommand):
    global sock
    str_command = serialize_dataclass(command)
    sock.send(type(command).CODE.encode())
    send_message(str_command, sock)

def waveform_sim(input_files: list[NamedFile], output_path: Path, folder_name: str):
    global sock, vcd_viewer

    command = WaveformSimCommand(output_path.name, input_files)
    t1 = time.time()
    send_command(command)

    result = receive_error_or_ack(sock)
    t2 = time.time()
    match result:
        case ErrorMessage(content):
            if content.strip().startswith("SRVRSEZ:"):
                print(f"{Fore.RED}{content.strip()[len("SRVERSEZ"):]}{Style.RESET_ALL}")
            else:
                print(colorize(content, f"verilog/testbench/{folder_name}"))
        case AckMessage():

            result_start = f"{success_title()} Ran testbench simulation in {round((t2 - t1), 3)}s."

            file_message = big_receive(sock).decode()
            output_file = deserialize_dataclass(file_message, NamedFile)
            output_file.to_disk(waveforms_folder)

            match vcd_viewer:
                case "vaporview":
                    print(result_start, f"Opening {Style.BRIGHT}{Fore.CYAN}{clickable_filepath(output_path, 2)}{Style.RESET_ALL} in VaporView.")
                    subprocess.run(f"code --reuse-window {shlex.quote(str(output_path))}", shell=True)
                case "gtkwave":
                    print(result_start, f"Opening {Style.BRIGHT}{Fore.CYAN}{clickable_filepath(output_path, 2)}{Style.RESET_ALL} in GTKWave.")
                    # gtkwave launches in background. the startup text is stderr
                    subprocess.Popen(f"gtkwave {shlex.quote(str(output_path))}", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                case "surfer":
                    print(result_start, f"Opening {Style.BRIGHT}{Fore.CYAN}{clickable_filepath(output_path, 2)}{Style.RESET_ALL} in Surfer.")
                    # run in background and suppress all prints
                    subprocess.Popen(f"surfer {shlex.quote(str(output_path))}", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                case None:
                    print(result_start, f"Saved output to {Style.BRIGHT}{Fore.CYAN}{clickable_filepath(output_path, 2)}{Style.RESET_ALL}")

def build_live_sim(input_files: list[NamedFile], folder_name: str):
    global sock, compiled_program

    command = BuildLiveCommand(input_files)
    t1 = time.time()
    send_command(command)

    result = receive_error_or_ack(sock)
    t2 = time.time()
    match result:
        case ErrorMessage(content):
            if has_template_mismatch_error(content):
                print(f"{error_title()} Your top module's inputs and outputs do not"
                      " seem to match the required form."
                      " See verilog/live_sim/ex_live/top.v for a"
                      f" template/example!{Style.RESET_ALL}")
                # TODO: update once more boards supported
            else:
                print("Server returned error message:")
                print(colorize(content, f"verilog/live_sim/{folder_name}"))
        case AckMessage():
            print(f"{success_title()} Built live simulation in {round((t2 - t1), 3)}s. Run with start_live_sim.")
            compiled_program = folder_name

def start_live_sim():
    global app, compiled_program

    command = StartLiveCommand()
    send_command(command)

    result = receive_error_or_ack(sock)
    match result:
        case ErrorMessage(content): # known to be plain text hardcoded message
            print(f"{Fore.RED}{content}{Style.RESET_ALL}")
        case AckMessage():
            print(f"Server started simulation of program {Fore.CYAN}{Style.BRIGHT}{compiled_program}{Style.RESET_ALL}. Launching GUI now.")
            # Run gui in a subprocess (fork) and give it the socket we already have
            if sys.platform != 'win32':
                subprocess.run(f"uv run ./python/gui__full_board.py {sock.fileno()}", shell=True, close_fds=False)
            else: # Windows requires fancy code; must use Popen because child must receive input after its creation
                live_sim_process = subprocess.Popen("uv run ./python/gui__full_board.py", stdin=subprocess.PIPE, shell=True, close_fds=False)
                child_pipe: IO[bytes] = live_sim_process.stdin # pyright: ignore[reportAssignmentType]
                shareable_socket = sock.share(live_sim_process.pid)
                child_pipe.write(base64.b64encode(shareable_socket))
                child_pipe.close() # send EOF before wait
                live_sim_process.wait()

class SuggestMode(Enum):
    NONE = auto()
    TB = auto()
    LIVE = auto()

def is_overwrite(text: str):
    return len(text) >= 2 and "-overwrite".startswith(text) and len(text) <= len("-overwrite")

def get_folder_names(path: Path):
    return [thing for thing in os.listdir(path) if not " " in thing and path.joinpath(thing).is_dir()]

def get_file_names(path: Path):
    return [thing for thing in os.listdir(path) if not " " in thing and not path.joinpath(thing).is_dir()]

class FolderNameCompleter(Completer):
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        super().__init__()
    def get_completions(self, document: Document, complete_event: CompleteEvent): 
        word = document.get_word_before_cursor(WORD=True) # splits only by whitespace (i.e. allows the . in .vcd)
        for thing in get_folder_names(self.folder):
            if thing.startswith(word) and self.folder.joinpath(thing).is_dir():
                yield Completion(thing, start_position=-len(word))

class FileNameCompleter(Completer):
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        super().__init__()
    def get_completions(self, document: Document, complete_event: CompleteEvent):
        word = document.get_word_before_cursor(WORD=True)
        for thing in get_file_names(self.folder):
            if thing.startswith(word) and thing.endswith(".vcd") and not self.folder.joinpath(thing).is_dir():
                yield Completion(thing, start_position=-len(word))

class WaveformSimCompleter(Completer):
    def get_completions(self, document, complete_event): # pyright: ignore[reportMissingParameterType
        split_line = document.text.split()[1:]
        args_length = len(split_line)
        if document.text.endswith(" "):
            args_length += 1

        # this logic feels a bit off but idk it's magic it works
        if args_length == 0:
            yield from FolderNameCompleter(testbench_folder).get_completions(document, complete_event)
        elif args_length == 1:
            yield from FileNameCompleter(waveforms_folder).get_completions(document, complete_event)

class BuildLiveSimCompleter(Completer):
    def get_completions(self, document, complete_event): # pyright: ignore[reportMissingParameterType
        split_line = document.text.split()[1:]
        args_length = len(split_line)
        if document.text.endswith(" "):
            args_length += 1

        if args_length == 0:
            yield from FolderNameCompleter(live_sim_folder).get_completions(document, complete_event)
           
def main_command_completer():
    return NestedCompleter.from_nested_dict(
        {
            "waveform_sim": WaveformSimCompleter(),
            "build_live_sim": BuildLiveSimCompleter(),
            "start_live_sim": None,
            "help": None,
            "exit": None
        }
    )


def get_server_image_tag():
    proc = subprocess.run('docker image ls fpga-sim-server --format "{{.Tag}}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    match proc.returncode:
        case 0:
            tag = proc.stdout.decode().strip()
            if tag == "":
                return None
            else:
                return tag
        case _:
            raise RuntimeError("docker image ls command failed.")
    
def get_latest_container_port(tag: str):
    '''Gets the port of the latest-started Docker server container.
    Error if there are no containers open or if Docker seems to be unopened.'''
    # Command prints string with 0 or more lines of this if successful:
    #   '{container hex id}|0.0.0.0:{port}->9834/tcp, [::]:{port}->9834/tcp'
    proc = subprocess.run(f'docker ps --format "{r"{{.ID}}|{{.Ports}}"}" --filter "ancestor=fpga-sim-server:{tag}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    match proc.returncode:
        case 0:
            output = proc.stdout.decode()
            for line in output.splitlines():
                port_string = line.split("|")[1]
                start = len("0.0.0.0:")
                end = port_string.find("->9834")
                return port_string[start:end]
            else:
                raise RuntimeError(f"No container for the server was found running. This means the program failed, not you. Perhaps Docker crashed between starting the program and now?")
        case _:
            raise RuntimeError(f"docker ps command failed; make sure that Docker Desktop is installed and is open.")

def colorize(err: str, folder: str | None = None):
    err = err.lstrip()
    if folder is not None:
        err = re.sub(r"user_inputs/", folder + "/", err)
    # cut off "Error: Exiting due to 1 error(s)"-type lines, we know the idea!
    err = re.sub(r"^.*Error: Exiting due to.*$", "", err, flags=re.MULTILINE)
    # cut off makefile build error line
    err = re.sub(r"^.*Makefile.*$", "", err, flags=re.MULTILINE)
    # remove lines that tell you to use a command e.g. ': ... Suggest see manual; fix the duplicates, or use --top-module to select top.'
    err = re.sub(r"( {8} *:.*use --(\w*)+(-\w*)* to.*\n)*", "", err, flags=re.MULTILINE)

    # remove lines suggesting always_latch or turning off latch lint.
    # PLEASE DO NOT USE LATCHES, KIDS!
    err = re.sub(r"^.*lint_off LATCH.*$", "", err, flags=re.MULTILINE)
    err = re.sub(r"^.*/warn/LATCH.*$", "", err, flags=re.MULTILINE)
    err = re.sub(r"^.*always_latch.*$", "", err, flags=re.MULTILINE)

    # remove Verilator manual line, Verilator specifics not likely relevant
    err = re.sub(r"^.*the manual at.*$\n", "", err, flags=re.MULTILINE)
    # color the individual error/warning lines and replace % with a space
    err = re.sub(r"%(?P<title>\w*(-\w*)?): (?P<content>.*\n( {8} *:.*\n)*)", f"{Fore.RED}{Style.BRIGHT} \\g<title>:{Style.RESET_ALL} {Fore.RED}{r"\g<content>"}{Style.RESET_ALL}", err)
    # color the line markers and the subsequent number-less pipe lines
    err = re.sub(r"(?P<front1>(\d| )*\|)(?P<content>.*)\n(?P<front2>(\d| )*\|)(?P<content2>.*)", f"{Fore.YELLOW}{r"\g<front1>"}{Style.RESET_ALL}{r"\g<content>"}\n{Fore.YELLOW}{r"\g<front2>"}{Style.RESET_ALL}{Style.BRIGHT}{Fore.RED}{r"\g<content2>"}{Style.RESET_ALL}", err)
    return err.rstrip()

def has_template_mismatch_error(err: str):
    # can't just use `‘class Vtop’ has no member named in string` due to
    #   ANSI color codes
    return bool(re.search(r"Vtop[^$]* has no member named", err, flags=re.MULTILINE))

class ContinueException(Exception):
    pass

def check_vcd_name(filename: str):
    if filename.split(".")[-1] != "vcd":
        raise ContinueException(f'output argument "{filename}" must end with .vcd')
    if filename != Path(filename).name:
        # will ultimately save directly to a defined output folder
        raise ContinueException(f'output argument "{filename}" is a path, not a pure name (e.g. "wave.vcd")')

def is_verilog(filename: str):
    extension = filename.split(".")[-1]
    return extension == "v"# or extension == "sv"

def crawl_input_directory(front_target: str, containing_folder: Path, folder_name: str):
    folder = Path(*containing_folder.joinpath(folder_name).parts[-3:])
    try:
        all_filenames = os.listdir(folder)
    except FileNotFoundError:
        raise ContinueException(f"./{folder} does not exist")
    except NotADirectoryError:
        raise ContinueException(f"./{folder} is a file, not a folder")

    v_filenames = [name for name in all_filenames if is_verilog(name)]

    if len(v_filenames) == 0:
        raise ContinueException(f"./{folder} contains no Verilog (.v) files")
    else:
        try:
            v_filenames.remove(front_target)
        except ValueError:
            raise ContinueException(f"./{folder} lacks a {front_target} file.")
        v_filenames.insert(0, front_target) # put at front to indicate top to Verilator
        
    file_paths = [Path(folder, name) for name in v_filenames]

    return [NamedFile.from_fp(open(file_path, "r"), close_after=True) for file_path in file_paths]

def clickable_filepath(filepath: Path, depth: int):
    return f"{Path(*filepath.parts[-depth:])}"

def waveform_viewer_wizard():
    print("Type in vaporview, surfer, gtkwave or none to select auto-open software, or exit to quit.")
    print("Press tab to list these options or complete a partial entry.")
    while True: # loop until they give a good option or enter exit
        viewer_choice = prompt("-> ", completer=WordCompleter(["vaporview", "gtkwave", "surfer", "none"], sentence=True), complete_style=CompleteStyle.READLINE_LIKE).strip().lower()

        match viewer_choice:
            case "vaporview":
                print("VSCode/VaporView selected")
            case "gtkwave":
                print("GTKWave selected.")
            case "surfer":
                print("Surfer selected.")
            case "none":
                viewer_choice = "NO_VIEWER"
                print("No viewer chosen. Waveforms will not be automatically opened.")
            case "exit":
                exit(0)
            case _:
                print("Invalid choice.")
                continue
        break # avoided only by _ branch

    settings_filepath.write_text(viewer_choice)

    print("Choice has been saved to ./python/waveform_viewer_choice.txt")

    return viewer_choice

def toolbar():
    full_text = get_app().current_buffer.text
    split_line = full_text.split()
    if full_text.endswith(" ") and split_line != []:
        split_line.append(" ") # add a fake word
    match split_line:
        case ["waveform_sim", *_]:
            return "Arguments: <folder> <filename.vcd> [-overwrite]"
        case ["build_live_sim", *_]:
            return "Arguments: <folder>"
        case ["start_live_sim", *_]:
            return "No arguments"
        case ["help"] | ["?"]:
            return "Help!"
        case ["exit"]:
            return "Bye!"
        case [_] | []:
            return "Press tab/shift-tab or up/down to select suggestions, and space to accept the highlighted one"
        case [_, _]:
            return "It appears you are typing in an invalid command"
        

def is_docker_open():
    proc = subprocess.run("docker info", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    match proc.returncode:
        case 0:
            return True
        case _:
            return False

def print_status(message: str, success: bool):
    '''Prints "Success:"/"Error:" in green/red followed by given message.
    Formats message so be careful about possible HTML in there messing it up.
    Python builtin module html has escape() function which may be required'''
    if success:
        print_formatted_text(HTML(f"<ansigreen>Success:</ansigreen> {message}"))
    else:
        print_formatted_text(HTML(f"<ansired>Error:</ansired> {message}"))

def error_exit(message: str, *, hint: str = "", cmd: str = ""):
    print_status(message, False)

    if hint != "":
        if cmd != "":
            print_formatted_text(HTML(f"<ansiyellow>Hint:</ansiyellow> {hint}:\n  <i>{cmd}</i>"))
        else:
            print_formatted_text(HTML(f"<ansiyellow>Hint:</ansiyellow> {hint}"))
    exit(1)

if __name__ == "__main__":
    if sys.prefix == sys.base_prefix: # if not in a venv give some guidance
        print("It appears this is being run without using the right uv environment; exiting.")
        if Path(os.getcwd()) != top_folder: # if in the wrong folder give command to get there, too
            print(f"To get to the proper folder run:\n\tcd {shlex.quote(str(top_folder))}")
            print("Then launch the program with:\n\tuv run ./python/client__shell.py")
        else:
            print("Instead run it from here with:\n\tuv run ./python/client__shell.py")
        print("For more info, view the README: https://github.com/TheHarmonicRealm/fpga-sim#Graphical-FPGA-Simulator")
        # TODO: include exported HTML version of README for offline usage?
        exit(1)

    if not settings_filepath.exists():
        print("Waveform viewer is unset. Which viewer would you like to use?")
        vcd_viewer = waveform_viewer_wizard()
    else:
        vcd_viewer = settings_filepath.read_text()

        clear_message = "Delete/clear out ./python/waveform_viewer_choice.txt and run again to change the setting!"

        match vcd_viewer:
            case "vaporview":
                if shutil.which("code") is not None:
                    print("VSCode/VaporView is selected to automatically open waveforms.")
                else:
                    print("VSCode does not seem to be installed. It may need to be added to your path (under the key 'code');")
                    print(" if you do this, you must restart the terminal for it to work.")
                    print("Waveforms will not be automatically opened for this session!")
                    vcd_viewer = "NO_VIEWER"

                print(clear_message)
            case "gtkwave":
                if shutil.which("gtkwave") is not None:
                    print("GTKWave is selected to automatically open waveforms.")
                else:
                    print("GTKWave does not seem to be installed. It may need to be added to your path (under the key 'gtkwave');")
                    print(" if you do this, you must restart the terminal for it to work.")
                    print(" Waveforms will not be automatically opened for this session!")
                    vcd_viewer = "NO_VIEWER"

                print(clear_message)
            case "surfer":
                if shutil.which("surfer") is not None:
                    print("surfer is selected to automatically open waveforms.")
                else:
                    print("surfer does not seem to be installed. It may need to be added to your path (under the key 'gtkwave');")
                    print(" if you do this, you must restart the terminal for it to work.")
                    print(" Waveforms will not be automatically opened for this session!")
                    vcd_viewer = "NO_VIEWER"

                print(clear_message)
            case "NO_VIEWER":
                print("\"No viewer\" option was chosen. Waveforms will not be automatically opened.")
                print(clear_message)
            case _:
                if vcd_viewer.strip() == "":
                    # print message as if it were deleted if the file is just cleared
                    print("Waveform viewer is unset. Which viewer would you like to use?")
                else:
                    print(f"./python/waveform_viewer_choice.txt has errant value.")
                    print("Running selection wizard again.")
                    print("Which viewer would you like to use?")
                vcd_viewer = waveform_viewer_wizard()

    if vcd_viewer == "NO_VIEWER":
        vcd_viewer = None


    try:
        socket_port = int(argv[1])
        docker_mode = False
    except IndexError: # No argument passed
        docker_mode = True

        if not shutil.which("docker"):
            error_exit("Docker is not installed (could not be found in system path).", hint="If you ran the installer, you may need to open a new terminal or restart your computer.")

        if not is_docker_open():
            if sys.platform != 'linux':
                error_exit("Docker is not running.", hint="You can open it from the command line with", cmd="docker desktop start")
            else: # Linux users are probably not on Docker Desktop per instructions
                error_exit("Docker is not running")

        # print("Launching Docker container.")

        required_tag = docker_tag_filepath.read_text().strip()
        
        try:
            available_tag = get_server_image_tag()
        except RuntimeError as e: # very unlikely. hard to have a reasonable hint here
            error_exit(f"Docker is open, but {e}", hint="Try running this program again. This is an unusual error.")

        if available_tag is None:
            error_exit(f"The necessary Docker image (fpga-sim-server:{required_tag}) is not installed", hint="Run docker pull as described in the README at", cmd="https://github.com/TheHarmonicRealm/fpga-sim")
        elif available_tag != required_tag:
            error_exit(f"fpga-sim-server:{available_tag} is loaded; software requires {required_tag}", hint="Run git pull and/or the docker pull command described in the README at", cmd="https://github.com/TheHarmonicRealm/fpga-sim")
        # Launch docker:
        #   preexec_fn is part of ignoring ctrl-C
        if sys.platform != 'win32':
            process = subprocess.Popen(f"docker run --rm -p 0:9834 fpga-sim-server:{required_tag}", text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setpgrp)
        else: # setpgrp unavailable on Windows. TODO: figure out equivalent code to ignore on Windows
            process = subprocess.Popen("docker run --rm -p 0:9834 fpga-sim-server:v1", text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        # wait until first print-out
        out_pipe: IO[str] = process.stdout # pyright: ignore[reportAssignmentType]
        out_pipe.readline()

        # print("Docker container started successfully. Launching client.")
        try:
            socket_port = int(get_latest_container_port(required_tag))
        except RuntimeError as e:
            print(error_title(), e)
            exit(1)
    except ValueError:
        print(f"Could not convert {argv[1]} to a port number. Exiting.")
        exit(1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.set_inheritable(True)
        try:
            sock.connect(("127.0.0.1", socket_port))
            if len(sock.recv(2048).decode()) == 0:
                raise ConnectionError("Not refused, but failed")
        except (ConnectionError, ConnectionRefusedError) as e:
            if docker_mode:
                print("Auto-started container rejected connection for some reason.")
                print("Quitting. Try running again; if it fails again, please contact the developer!")
            else:
                print(f"Failed to connect to the native server that may be running at port {socket_port}. Make sure it is running and that the port number matches what it output!")
            print(f"Original exception: {e}")
            exit(1)

        if docker_mode:
            pass
            # print(f"Connected to automatically-started Docker container running at port {socket_port}")
        else:
            print(f"Connected to native server running at port {socket_port}")

        app = None

        signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-C


        kb = KeyBindings()

        # browse menu with tab/shift-tab or up/down
        @kb.add("up")
        def _(event: KeyPressEvent):
            event.current_buffer.start_completion()
            event.current_buffer.complete_previous()
        @kb.add("down")
        def _(event: KeyPressEvent):
            event.current_buffer.start_completion()
            event.current_buffer.complete_next()
        @kb.add("c-i") # tab
        def _(event: KeyPressEvent):
            event.current_buffer.start_completion()
            event.current_buffer.complete_next()
        @kb.add("s-tab") # shift-tab
        def _(event: KeyPressEvent):
            event.current_buffer.start_completion()
            event.current_buffer.complete_previous()

        # apply keybindings. gets full functionality with small compromise!
        # sesh = PromptSession("> ", completer=main_command_completer(), key_bindings=kb, bottom_toolbar=toolbar)

        # call this to have experience like old one on Mac/Linux.
        #   going with this to have the least disruption
        #   TODO: support the fancy one with a setting. I think it's
        #   *good* but could be distracting
        sesh = PromptSession("> ", enable_history_search=True, complete_while_typing=False, completer=main_command_completer(), complete_style=CompleteStyle.READLINE_LIKE, history=InMemoryHistory())

        while True:
            try:
                command_string = sesh.prompt()
            except KeyboardInterrupt:
                continue

            words = command_string.split()
            if len(words) == 0:
                continue

            command = words[0]
            args = words[1:]

            try:
                match command:
                    case "waveform_sim":
                        match args:
                            case [folder, filename, *_]:
                                waveforms_folder.mkdir(exist_ok=True)
                                # not visible at all to user but make the path
                                #   relative instead of absolute.
                                # when debugging I saw the giant full-length
                                #   path passed to Surfer and it made me sad
                                output_path = waveforms_folder.joinpath(filename).relative_to(top_folder)

                                overwrite = False

                                if len(args) > 3:
                                    raise ContinueException(f"{command} expects only two or three args")

                                elif(len(args) == 3):
                                    if(is_overwrite(args[2])):
                                        overwrite = True
                                    else:
                                        raise ContinueException(f"{command} last arg should be -overwrite or a shortening of that.")

                                # may raise ContinueException
                                check_vcd_name(filename)
                                
                                if (not overwrite) and output_path.is_file():
                                    raise ContinueException(f"cannot overwrite existing file {clickable_filepath(output_path, 1)}; pass -ov option if you wish to allow overwriting.")

                                files = crawl_input_directory("tb.v", testbench_folder, folder)
                                waveform_sim(files, output_path, folder)
                            case _:
                                raise ContinueException(f"{command} args are <folder> <filename.vcd> [-ov]")
                    case "build_live_sim":
                        match args:
                            case [folder]:
                                files = crawl_input_directory("top.v", live_sim_folder, folder)
                                build_live_sim(files, folder)
                            case _:
                                raise ContinueException(f"{command} needs folder argument")
                    case "start_live_sim":
                        if len(args) != 0:
                            raise ContinueException(f"{command} takes no args")
                        start_live_sim()
                    case "exit" | "quit":
                        exit(0)
                    case "help" | "?" | "-h":
                        print("Available commands: \n* build_live_sim <folder>\n* waveform_sim <folder> <filename.vcd> [-overwrite]\n* start_live_sim\n* exit")
                    case _:
                        print("Unrecognized command")
            except ContinueException as e:
                print(f"{error_title()} {e}")
                continue # when help is called or a bad argument is passed
