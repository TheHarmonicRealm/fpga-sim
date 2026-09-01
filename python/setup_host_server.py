# Run this to copy all the files to run the server natively on your machine,
# if Verilator is installed, to their own folder.
import shutil
from pathlib import Path
from sys import argv

from client__paths import top_folder, docker_tag_filepath

if shutil.which("verilator") is None:
    print("Verilator is not in your terminal's path. Please install it or the server set up by this will not work.")
    print("Try running this in a new terminal tab if you just installed Verilator.")
    exit(1)

match argv:
    case [_]:
        host_folder = top_folder.joinpath("host_server")
        custom_path = False
        overwrite = False
    case [_, "-ov"]:
        host_folder = top_folder.joinpath("host_server")
        custom_path = False
        overwrite = True
    case [_, custom_path]:
        host_folder = Path(custom_path)
        custom_path = True
        overwrite = False
    case [_, custom_path, "-ov"]:
        host_folder = Path(custom_path)
        custom_path = True
        overwrite = True
    case _:
        print("Unexpected arguments passed")
        exit(1)


for char in str(host_folder.resolve()):
    if char.isspace():
        if custom_path:
            print("Target path contains a space. GNU make, used by Verilator, does not support running in paths with spaces.")
            print("Please pass a different path.")
            exit(1)
        else:
            print("Path containing this project contains a space. GNU make, used by Verilator, does not support running in paths with spaces.")
            print("You can pass your own custom target path as the argument to this script.")
            exit(1)

if host_folder.exists():
    if overwrite or len(list(host_folder.iterdir())) == 0: # also overwrite if empty
        shutil.rmtree(host_folder)
    else:
        print(f"Server folder {host_folder} already exists and has things in it. Please clear it out and run again.")
        exit(1)

try:
    host_folder.mkdir()
except FileNotFoundError:
    print(f"Could not create server folder {host_folder}; all of its parents must exist!")
    exit(1)

to_copy = [
    top_folder.joinpath("python/server__manager.py"),
    top_folder.joinpath("python/shared__util.py"),
    top_folder.joinpath("python/extract_ports.py"),
    top_folder.joinpath("server_materials/Makefile"),
    top_folder.joinpath("server_materials/Makefile_obj"),
    top_folder.joinpath("server_materials/port_ref.cpp"),
    top_folder.joinpath("server_materials/port_ref.h"),
    top_folder.joinpath("server_materials/simulator_driver_template.cpp"),
    top_folder.joinpath("server_materials/string_dict_tools.cpp"),
    top_folder.joinpath("server_materials/string_dict_tools.h"),
    top_folder.joinpath("server_materials/run_waveform.sh"),
    docker_tag_filepath
    ]

for file in to_copy:
    shutil.copy(file, host_folder)

host_folder.joinpath("user_inputs").mkdir()