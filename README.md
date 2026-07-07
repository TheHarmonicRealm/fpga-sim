# Graphical FPGA Simulator

This is a cross-platform program designed to help teach Verilog/SystemVerilog to
students new to programming. It provides a friendly command-line interface, both
to run Verilog testbenches and to run synthesizable code interactively on a
"virtual FPGA board" (referred to as "live simulations").

Primary development is on Mac, with significant testing on Windows and Ubuntu.
The software has [low performance requirements](os-hardware) and I believe it
will run well on almost any computer from the past few years with a recent
operating system.

This software was first used in spring 2026 for ECE 2029
(*Introduction to Digital Circuit Design*) at Worcester Polytechnic Institute
(WPI) in Worcester, Massachusetts, for a class of about 120 students.
If you are an educator interested in using it for a class, please contact me via
email or LinkedIn (both listed at my website, https://www.nobodybutnoah.com/).
I would love to hear from people!

## Live sim demos

This program provides four "virtual boards," three of which are shown here
running private example programs; if you are an instructor I can provide it
so you can test them on something less trivial than the public programs.
[You can also make additional boards](#creating-more-live-simulator-boards)
tailored to specific student assignments if you have a bit of Python
experience, and I am working to make it even easier.

|  Simulator  | Light mode video | Dark mode video |
| ----------- |------------------|-----------------|
| Calculator  |  <video src="https://github.com/user-attachments/assets/108a40d1-4020-4faf-9412-b4e7bbbdb132"></video>   | <video src="https://github.com/user-attachments/assets/e49f20da-9169-4c5f-824d-552be7e8b0af"></video>
| Dot matrix  |        <video src="https://github.com/user-attachments/assets/d38b5d25-d4c8-4af9-be07-1995f8975820"></video>         |      <video src="https://github.com/user-attachments/assets/d2a18546-ff38-4cd9-b04f-e3ec97e34079"></video>          |
| Classic     |      <video src="https://github.com/user-attachments/assets/bcf54133-e3f5-4eb3-a1d4-95b62fc99866"></video>           |       <video src="https://github.com/user-attachments/assets/5381d70a-d619-407b-9ad4-64616ce2cbae"></video>         |



## System requirements

<a id="os-hardware"></a>
### Operating systems/hardware

Updated July 2, 2026, based on [Qt's requirements](https://doc.qt.io/qt-6/supported-platforms.html)
and on Docker's. Docker is the bounding dependency for all of these; if you obtain
an older version, it may work on unsupported operating systems.
[Native mode](#native-mode) does not require Docker, though it requires
more advanced computer skills to set up.

* **Mac**:
    * MacOS 14 Sonoma, 15 Sequoia, or 26 Tahoe
        * Docker supports the last two versions of MacOS
        (see [Docker's Mac requirements](https://docs.docker.com/desktop/setup/install/mac-install/#system-requirements)).
    * All supported models have 8GB+ of RAM, well over Docker's 4GB minimum.

* **Windows**:
    * Windows 11 version 22H2 (build 22631) or higher
    * Windows 10 version 22H2 (build 19045) or higher
        * Docker supports the currently-serviced versions of Windows
        (see [Docker's Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/#system-requirements)),
        which do not include standard Windows 10 Personal, but I have heard from some
        students that it works without issue.
            * To be clear, I do not endorse using Windows 10 without security updates.
    * At least 8GB of RAM.
        * It may be possible to configure WSL2 to use less RAM and run Docker
        on under 8GB.

* **Linux**:
    * See these two links for information about Linux version support:
        * [Docker Engine's supported distributions](https://docs.docker.com/engine/install/)
        * [Docker Desktop's system requirements](https://docs.docker.com/desktop/setup/install/linux/#general-system-requirements)
        (which are presumably greater than or equal to those of Engine)
    * At least 4GB of RAM.

### Required software

> [!Caution]
> The recommended programs are trustworthy†, but please do not download random
software without thinking about it. The internet is a scary place!

Instructions to install each of these are embedded in the list of steps.
If any of these are already on your computer, there is no need to reinstall
them. If you want, you can install the required software yourself then skip to
[step 7](#step-7).

* [git](https://git-scm.com/install/) to download the code
    * Check if you have it: run `git --version` in your terminal
* [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage Python
    * Check if you have it: run `uv --version` in your terminal
* Docker, which is how the software backend runs in an Ubuntu VM
    * Windows/Mac: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
    * Linux: [Docker Engine](https://docs.docker.com/engine/install/)
* [Visual Studio Code](https://code.visualstudio.com/) or another IDE, including extensions for a Verilog syntax
highlighter
    * [Recommended VSCode Verilog syntax highlighter](https://marketplace.visualstudio.com/items?itemName=eirikpre.systemverilog)
* A waveform viewer
    * This program supports automaticaly opening with VSCode's
    [VaporView](https://marketplace.visualstudio.com/items?itemName=lramseyer.vaporview)
    extension, [GTKWave](https://gtkwave.github.io/gtkwave/index.html),
    or [Surfer](https://gitlab.com/surfer-project/surfer), but any program that
    can open .vcd files can be used manually

## Installation walkthrough

1. Open your terminal app. Others should work fine if you are familiar with
the terminal and want to use them, but the appropriate built-in ones are:
* Terminal on Mac
* Windows Terminal on Windows
* Terminal, Konsole, or something else on Linux (varies by distro)

In the terminal, [check your CPU architecture](STUDENT_INSTRUCTIONS.md#identifying-processor-architecture),
as described in the student instructions.

> [!Caution]
> On Windows, make sure you are in Windows Terminal, and that the tab is
labeled PowerShell, **not** Command Prompt.

2. Download and install Docker:

**Windows/Mac**:
* Download [Docker Desktop](https://www.docker.com/products/docker-desktop/)
for your appropriate OS and CPU architecture.
Open it when done to start the installation process, which takes 5-10 minutes.
**You can continue until [step 7](#step-7) while waiting for this to finish.**
After installation, open it if it does not automatically open itself.
* On Windows, it will likely prompt you to update WSL, which is the Windows
component Docker runs on; it will display a terminal command, which you must
paste into your terminal and run. When that process says it is done, return to
Docker and press the "try again" button.
* You may need to restart after installing on Windows. It seems to vary by
computer.
* When prompted to make an account, you can skip. It is unnecessary for this
program.
* You can launch Docker from the command line with `docker desktop start`.
I recommend disabling the "Open Docker Dashboard when Docker Desktop starts"
option in Docker Desktop's settings.
    * On Mac and possibly Windows, Docker will request a permission described
    similarly to "network port mapping". Please accept this to allow the
    container to connect to the command line program.

**Linux**:
* Install [Docker Engine](https://docs.docker.com/engine/install/);
Docker Desktop is unnecessary for this software, and the core "engine"
has support for more distributions than the "Desktop" GUI. Setup using apt, as
described on Docker's site, was very easy for me on Ubuntu.
* You must follow the [post-install instructions](https://docs.docker.com/engine/install/linux-postinstall#manage-docker-as-a-non-root-user)
and make Docker usable as a non-root user for my software to be able to
access it. I had to restart in order for these to apply, though it seems
to vary for some systems.

3. Install Visual Studio Code (not mandatory but highly recommended):

**All platforms**:
* [Download Visual Studio Code](https://code.visualstudio.com/Download).
Just like Docker Desktop, open it when the download finishes, and an
installation process will start.
    * After VSCode is installed, install these two extensions:
        * [Verilog language support](https://marketplace.visualstudio.com/items?itemName=eirikpre.systemverilog)
        * [VaporView](https://marketplace.visualstudio.com/items?itemName=lramseyer.vaporview) VCD viewer

**If you are not using VSCode**:
Install [GTKWave](https://gtkwave.github.io/gtkwave/index.html) or
[Surfer](https://gitlab.com/surfer-project/surfer) to somewhere that can be
found by the terminal from your system path. GTKWave is not recommended on
Windows unless you are experienced with compiling software.
[Surfer can also be used in the browser](https://app.surfer-project.org/)
(without an auto-opening feature, and maybe with bad performance).
If you use another VCD viewer and like it, please contact me and I may add it
as an officially supported viewer to automatically open waveforms.

4. Install uv:
* Windows: use [uv's standalone Windows installer](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2)
(paste the **first listed command** into your terminal to run a script).
    * If this fails, you can try installing uv via pip instead:
        * First try running `py -m ensurepip`.
            * If this returns a message like "requirement already satisfied..."
            or "installing pip" followed by some loading bars, continue to the
            next bullet point once the process finishes.
            * If this returns a message like "py not found",
            [install the latest version of Python 3.14](https://www.python.org/downloads/),
            and when that's done open a new terminal tab and try the ensurepip
            command again.
        * Once you have pip, install uv using `py -m pip install uv`.
            * If installed in this manner, uv is invoked eith `py -m uv`
            in place of `uv` (so `py -m uv run ...` etc)
* Mac/Linux: use [uv's standalone Mac/Linux installer](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_1)
(paste the listed command in the terminal to run a script).

5. Install git:

* Windows: download the [git installer for Windows](https://git-scm.com/install/windows),
for your appropriate CPU architecture.
Open it when done to start the installation process, which will consist of a lot
of screens, all of which you should choose the defaults on.
* Mac: use `xcode-select --install`. This gets you various tools including git.
Note that you will need to run `sudo xcodebuild -license accept`
(which will prompt for your password) sometimes when your computer updates
in order to re-accept Apple's TOS and use git.
* Linux: [git install instructions for Linux](https://git-scm.com/install/linux)
(lists various package manager commands)

6. Close VSCode and your terminal app completely.

* The point of this is to make sure any terminal you will open from now can
find uv, git, and VSCode.

<a id="step-7"></a>
7. Download the code and pull the Docker image:

* In your terminal, run `cd ~/Documents` to go to the Documents folder.

> [!Caution]
> **If you are on Mac**, make sure Documents is not an iCloud folder, or
> [you will run into issues later](https://stackoverflow.com/a/79852060)!
> 
> In the terminal, run `open .` to view the Documents folder in Finder. If
> the "path bar" at the bottom of the window is not visible, press
> <kbd>⌥</kbd>+<kbd>⌘</kbd>+<kbd>P</kbd> to show it:
> 
> * **If the leftmost item in the path bar is not iCloud Drive**, continue on
> as normal.
> 
> * **If the leftost item in the path bar *is* iCloud Drive**, you need to use
> a different folder:
>     * In the terminal, run `cd ~` to go to your user folder.
>     * Run `mkdir fpga-sim-app` then `cd ./fpga-sim-app` to make and enter a new folder


* "Clone" this git repository. This will put the software in a new folder within
Documents:

    ```
    git clone https://github.com/TheHarmonicRealm/fpga-sim.git
    ```

* Open the folder it makes in your IDE. For VSCode do:

    ```
    code ./fpga-sim
    ```

> [!Note]
> Make sure Docker is open when pulling the image and when running
the simulator program. They will visibly fail if it is not.

* Pull the appropriate Docker image:

    * x86:

        ```
        docker pull --platform linux/amd64 ghcr.io/theharmonicrealm/fpga-sim-server:v2
        ```

    * ARM:

        ```
        docker pull --platform linux/arm64 ghcr.io/theharmonicrealm/fpga-sim-server:v2
        ```

8. From the `fpga-sim` directory
(the IDE's integrated terminal is convenient and will start in the right place;
open it with <kbd>ctrl</kbd>+<kbd>`</kbd> in VSCode)
launch the program with:

```
uv run ./python/client__shell.py
```

* This will take a little bit the first time, as uv must
set up a virtual environment, which entails automatically downloading packages
and possibly a new Python version. After the first time,
the program is still run with this command and should not have any
unusual startup delay.

> [!Note]
> You cannot run the script with a different command. uv ensures you are on the correct Python
version and have the necessary packages available.

## Program usage

The client gives you a command-line interface (CLI), where it requests terminal
input and you enter commands, resembling the behavior of a shell.

You can run three specific commands here, along with `exit` to quit the client
and server, and `help` to list the commands.

The client provides suggestions when you press tab, and you can cycle through
the current session's history using the up and down arrows, similarly to the
external shell.

Suggestions are selected based on the index of the argument you are currently
typing, to properly recommend folders or existing output files.

Note that where an argument is shown in angle brackets (<>), you are to replace
its value with your own, **without brackets.**
For example, `print <name>` would be called as `print Goddard`,
NOT `print <Goddard>`.

### Waveform testbench simulation
Place your testbench and modules in a new folder within the `verilog/testbench`
folder. The top testbench module must be called `tb`; see
`verilog/testbench/ex_tb` for a barebones example you can use as a template.
The folder and module names must contain only underscores and letters.
There are a couple things to note about what your modules must look like:

* As in the provided example the lines
`$dumpfile("$DUMP_FILENAME");` and `$dumpvars(0, tb);` must be the first
things in your `initial begin` block.
* `$display` statements will not be forwarded back to the user.
* End your testbench with `$finish`, like the example; using `$stop`, or not
having an ending command, will crash the simulator.

All filenames must match their module names (i.e. `lights` ↔︎ `lights.v`, etc).
This rule goes for live simulation, too.

Run the testbench with `waveform_sim <input_directory> <output_filename.vcd> [-overwrite]`.
This may take a few minutes in extreme cases.

> [!Note]  
> On Windows, when a waveform sim is run and the output opens automatically in
> VSCode, if it shows an error like "this file has an error and can't be opened",
> delete the file in the `python` folder called `waveform_viewer_choice.txt`.
> Close the program, run it again, and enter "None" when prompted to choose a waveform viewer.

If `-overwrite`, or any shortening of it (`-o` or longer), is provided as the
third argument, the output file will be overwritten if it already exists.
Otherwise, an error is printed if it already exists, to avoid accidents.
The first time you run this, it will have you choose which waveform viewer, if
any, to automatically open waveforms in. You can later change your setting
by deleting the file `python/waveform_viewer_choice.txt` and running the
program again.

* **Example call:** `waveform_sim ex_tb wave.vcd`
* **Example call (allowing overwrite):** `waveform_sim ex_tb wave.vcd -ov`

> [!Note]  
> Unlike live simulation, testbench/waveform simulation does not have separate build and run steps.

### Live simulation
This program currently comes with four "virtual boards" for live simulation.
Three provide a clock signal, while one is very simple and does not.

<details>

<summary>List of provided boards</summary>

Example code for the first two boards is available at
`verilog/live_sim/ex_classic` and `verilog/live_sim/ex_dotmatrix`. The
calculator is way harder to make an example for without "giving it away" but a
non-runnable template is at `verilog/live_sim/ex_calculator`. The final one,
which is just the switches and LEDs from the first two boards, for an example
of a board without a clock, made only for combinational logic, also does not
have example code.

**Classic board**

This board is based on the real devkit formerly used for WPI's course. It has:
* Four red seven-segment digits
(controlled with active-low pattern and digit select signals)
* A row of 16 on-off switches, aligned with a row of 16 green "LEDs"
* 5 buttons in a plus shape, multiple of which can be pressed if clicked while
holding shift
* A 60 Hz clock (120 frames per second)

**Dot-matrix board**

This board is the same as the classic, except the seven-segment display is
replaced with a four-digit "dot matrix" display. Each digit is 3x7 pixels.
It is active-high for the digit-select and pattern signals.

**Calculator board**

This board has a dot-matrix display like the other board, but replaces
the controls with the layout of a four-function calculator. Its display is
3x5 pixels per digit. This is an example of what can be made for specific
assignments and projects that use the software. Modifying it to have more
or less buttons, more digits, and/or differently shaped digits would not be
hard for a moderately experienced programmer.

**Switches board**

This board has the 16 switches and 16 LEDs from the classic/dotmatrix boards,
and no clock.

</details>


Write Verilog or SystemVerilog code with the same inputs and outputs as the
examples, and compile it with the `build_live_sim <input_directory> <simulator>`
command. For example, the dot matrix example compiles with the below command:

```
build_live_sim ex_dotmatrix dotmatrix
```

After successfully building, launch the simulator with:
```
start_live_sim
```

> [!Note]
> Linux users: when trying to run live simulation, which uses Qt to create a
> GUI, you may get an error saying something like
> `Could not load the Qt platform plugin "xcb"`. To resolve this,
> [install the appropriate XCB cursor plugin for your distribution](https://stackoverflow.com/questions/77725761/).

Notes:
* The folder and module names must contain only underscores and letters.
* If you edit any files inside a folder you have built, you will be warned
when starting so you don't incorrectly run it thinking it is the most updated
program. This warning has a `[Y/n]` prompt, meaning you must type "n" exactly
and hit enter, or it will start.
* Display statements are supported (but not heavily tested yet).
* On some platforms, this window might not automatically go the front,
so if you don't see anything after a couple seconds check your window
switcher.
* The plus-shaped buttons will stay pressed if you are holding shift when
you release the mouse.
* This window can be quit normally with the window's X button or with
<kbd>ctrl</kbd>+<kbd>W</kbd>
(Mac: <kbd>⌘</kbd>+<kbd>Q</kbd> or <kbd>⌘</kbd>+<kbd>W</kbd>).
It can be paused and unpaused with <kbd>P</kbd> or the button at the bottom.
* There are two checkboxes at the bottom next to the FPS counter:
    * Frameless mode, which hides the window chrome.
    * Always-on-top mode. This will not be shown if you are on Wayland, which
    does not let programs enable this mode; instead right-click the window's top
    bar and select the relevant option to get the same effect.
  

* In the CLI, if you press tab you can get suggestions and
autocomplete for commands, and, in the second argument position, folder names
for `waveform_sim`/`build_live_sim`. There is also up/down history browsing
like in a real shell.

#### Creating more live simulator "boards"

Starting with v2, this program can support multiple live simulator boards
without needing a new Docker image. Currently, this requires some knowledge of
Python and a little knowledge of Qt, with new simulators needing two parts:
* A Python script of any name (though I recommend naming it like the others,
prefaced with `gui__`) stored in the `python` folder. Base this on one
of the provided boards.
* New entries in the `user_board_data.toml` file to point to the file and list
the widths of the new board's input and output ports.
    * Base these on `board_data.toml` but place them here to not have
    merge conflicts when updating via `git pull`.

## Updating the software

Use `git pull` to update the project. This will not modify your waveform viewer
settings or delete your code. However, if you have modified any of the project's
source files, you should revert your changes before pulling.

The Docker image also needs to update sometimes. Whenever you run the software,
it will check whether the Docker image is up to date. If it is not, it will
print out the current Docker pull command to update it.

## Additional notes

### Native mode
While Ubuntu is the primary target for Verilator, it also compiles on
Mac (both Clang and G++) and Windows, and some other systems;
see [Verilator's install instructions](https://verilator.org/guide/latest/install.html#os-requirements)
for information about compiling it.

If Verilator is installed on your computer, this program has an alternative mode
to run the server directly without Docker.

**This mode is not recommended for students without previous terminal experience.**

<details>

<summary>Native mode instructions</summary>

On Mac, using the built-in Clang to compile Verilog, this works smoothly, with
the requirements I needed downloaded from brew, and I am sure it works well on
most Linux distributions.
Windows support for Verilator appears to be more rough; if you attempt to
install Verilator and natively run the server on any platform, please let me
know about your experience, successful or not!

Using this mode:
1. From the top fpga-sim folder, set up the server with:

    <!-- TODO: maintain this script!!! perhaps could scrape the copying list from
    the Dockerfile somehow -->
    ```
    uv run python/setup_host_server.py <path>
    ```

    With no arguments, this will place the server in `fpga-sim/host_server`, or
    it otherwise will place it in `<path>/host_server`.
    A rule enforced by my setup script, which cannot be circumvented, is that
    **the path must contain no spaces**, because GNU make is used by the server.
    This script will also fail with a warning if Verilator has not yet been
    installed.

2. Open the server's folder in a new terminal. The only dependencies for the
    server are included with Python, so uv is unnecessary here. Just run it
    with the `python3.14` alias that uv automatically created when setting up
    the client venv:

    ```
    python3.14 server__manager.py
    ```

    The server will print the port number it is running at.

3. Run the client from the fpga-sim project, the same way as described in
    the main instructions' step 3, but pass the port number as its third
    argument. The program will detect this and connect to the native server you
    opened, rather than starting up a docker container.

    The script should operate the same, except that when the server is stopped
    the last-built live sim persists rather than being lost on closing.

</details>

### Future plans

Here are some things I intend to add in the future:
* Support for Podman, an alternative container system which has some benefits
(CLI-only option for Mac/Windows users, possibly better performance)
    * If I can make native mode easier to use, and can confirm it works well on
    Windows, I might make it the primary way to use the program and skip
    containers entirely.
* More virtual boards.
* Changes to the virtual board system to require less effort on the part of
people making new ones.
    * A "DSL" (probably just Python-based) to assemble Qt layouts for a virtual
    board using the existing widgets would be really cool.
* Support for display statements in testbenches.
* Better networking code so it's easier to send things back and forth.
Currently the coordination between the server and client is pretty annoying to
write. I imagine there is a library out there that could let me write
`client__shell.py` and `server__manager.py` in a more pleasant way.
* Installation to a central location, to separate user programs from the app's
code.
    * If done right this would make it more feasible to install on lab computers
    for multiple users, though if that were to happen there would be new 
    security considerations I haven't really had in mind.

---
†No warranty given by developer, etc.
