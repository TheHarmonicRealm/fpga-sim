import subprocess
from html import escape
from pathlib import Path
from sys import argv

from prompt_toolkit import HTML, print_formatted_text


def print_error(text: str):
    print_formatted_text(HTML(f"<ansired><b>•</b></ansired> Error: {escape(text)}"))

def print_success(text: str):
    print_formatted_text(HTML(f"<ansigreen><b>•</b></ansigreen> {escape(text)}"))

def build_native(arch: str, image_name: str):
    try:
        subprocess.check_call(["docker", "buildx", "build", "-t", image_name, "."])
    except subprocess.CalledProcessError:
        print_error(f"Native {arch} build failed (see Docker errors above)!")
        exit(1)
    else:
        print_success(f"Native {arch} build was successful!")

def build_all(arch: str, image_name: str):
    '''Builds in series. Takes WAY longer to do in parallel.
    E.g. on my Mac, ARM is ~9 mins, x86 is ~15, but a full parallel build
    took >60 mins the one time I did it!'''
    if arch == "ARM":
        arch1 = "linux/aarch64"
        arch2 = "linux/amd64"
        other_arch = "x86"
    else:
        arch1 = "linux/amd64"
        arch2 = "linux/aarch64"
        other_arch = "ARM" # for display purposes

    print(f"Building {arch1}")

    try:
        subprocess.check_call(["docker", "buildx", "build", "--platform", arch1, "-t", image_name, "."])
    except subprocess.CalledProcessError:
        print_error(f"Native {arch} build failed (see Docker errors above)!")
        exit(1)
    else:
        print_success(f"Native {arch} build was successful! Continuing on to {other_arch} build.")

    try:
        subprocess.check_call(["docker", "buildx", "build", "--platform", arch2, "-t", image_name, "."])
    except subprocess.CalledProcessError:
        print_error(f"{other_arch} build failed (see Docker errors above)!")
        exit(1)
    else:
        print_success(f"Both builds were successful!")


native_architecture = subprocess.run(["docker", "info", "--format", "'{{ .Architecture }}'"], stdout=subprocess.PIPE, check=True).stdout.decode()
native_architecture = native_architecture.strip().strip("'") # has outer single quotes
if native_architecture == "x86_64":
    native_architecture = "x86"
elif native_architecture == "aarch64":
    native_architecture = "ARM"
else:
    print_error(f"Unrecognized architecture reported by Docker: {native_architecture}. Quitting!")
    exit(1)

tag = Path("docker_tag.txt").read_text().strip()
image_name = f"ghcr.io/theharmonicrealm/fpga-sim-server:{tag}"

try:
    match argv:
        case [_]:
            build_native(native_architecture, image_name)
        case [_, "all"]:
            build_all(native_architecture, image_name)
        case _:
            print_error("Invalid argument. Either takes no arguments to build for "
                f"this computer's architecture ({native_architecture}), "
                "or \"all\" to build in parallel for both ARM and x86")
            exit(1)
except KeyboardInterrupt:
    print_error("User canceled with ctrl-C")
    exit(1) # don't print that