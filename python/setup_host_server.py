# Run this to copy all the files to run the server natively on your machine,
# if Verilator is installed, to their own folder.
import shutil
from pathlib import Path
from sys import argv

from client__paths import top_folder

if shutil.which("verilator") is None:
    print("Verilator is not in your terminal's path. Please install it or the server set up by this will not work.")
    print("Try running this in a new terminal tab if you just installed Verilator.")
    exit(1)

try:
    host_folder = Path(argv[1]).joinpath("host_server")
    custom_path = True
except IndexError:
    host_folder = top_folder.joinpath("host_server")
    custom_path = False

for char in str(host_folder.resolve()):
    if char.isspace():
        if custom_path:
            print("Target path contains a space. GNU make, used by Verilator, does not support running in paths with spaces.")
            print("Please pass a different path.")
        else:
            print("Path containing this project contains a space. GNU make, used by Verilator, does not support running in paths with spaces.")
            print("You can pass your own custom target path as the argument to this script.")
        exit(1)

try:
    host_folder.mkdir(exist_ok=False)
except FileExistsError:
    print(f"Server folder {host_folder} already exists.\nSupporting overwrites of a folder that contains only a server, using argparse to read options, is a todo for now") # TODO: do this
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
    top_folder.joinpath("server_materials/run_waveform.sh")
    ]

for file in to_copy:
    shutil.copy(file, host_folder)

host_folder.joinpath("user_inputs").mkdir()