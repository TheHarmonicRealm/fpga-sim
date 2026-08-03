import ast
import socket
import sys
import textwrap
import threading
import time
from collections.abc import Mapping
from statistics import mean
from typing import Final, override

from colorama import Fore, Style
from gui__util import reconstruct_socket_unix, reconstruct_socket_windows
from gui__widgets import (
    AppStyle,
    BoardInput,
)
from PySide6.QtCore import QDeadlineTimer, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QLabel
from qt_helpers import (
    EmptyWindow,
    PushButton,
    hbox_factory,
    make_action,
    make_checkbox,
    pseudo_disable,
    vbox_factory,
)
from shared__util import big_receive, dict_diff, send_message


def deserialize_dict(d: str) -> dict:
    return ast.literal_eval(d)

def error_quit(error: str):
    '''Call this instead of raising errors to (probably) avoid a full crash in
    scenarios where the virtual board is miswritten'''
    print(f"{Fore.RED}{Style.BRIGHT}Error:{Style.RESET_ALL} {error}")
    QTimer.singleShot(0, QApplication.quit)

class BaseGUIWindow(EmptyWindow):
    # triggered whenever a model input changes, causing an update to `latest`, the dict sent upwards every non-paused frame
    input_changed = Signal(dict) # really InputDict — but undefined here and not really significant
    # triggered whenever the model output beams back down. COULD: change to only emit when the output is modified but it seems low-overhead
    output_changed = Signal(dict) # really OutputDict — but undefined here and not really significant
    # triggered at the start of each "frame", to send latest up
    input_time = Signal()
    # triggered when the server gives us a response to our sending up of latest
    pinged = Signal()
    def __init__(self, sock: socket.socket, program_name: str, sim_name: str, *, target_fps: int = 60, sleep_resolution: float = .0001, show_reset: bool = True, show_pause: bool = True, fixed_size: bool = True):
        # sim_name is currently unused. didn't love including in window title
        # but might put elsewhere on the actual window later
        self.win_title = f"“{program_name}”"
        super().__init__(f"{self.win_title} (running)")
        self.sock = sock
        self.target_fps = target_fps
        self.sleep_resolution = sleep_resolution


        self.listener_done = threading.Event()
        self.have_quit = threading.Event()

        # important: put thread under self or gc destroys it immediately
        self.listen_thread = ListenThread(self)

        # must be behind singleshot delay because this runs before child
        #   constructor, so the signals aren't connected yet
        QTimer.singleShot(0, self.listen_thread.start)

        self.input_widgets: list[BoardInput] = []

        # first two are redefined in subclasses. defined here to avoid type-checker errors
        #   in shared functions
        self.output_state = {}
        self.input_state = {}
        self.latest = {}
        self.previous = {}

        self.pinged.connect(self.update_fps)
        self.input_time.connect(self.update_server)
        self.input_changed.connect(self.update_latest)
        self.output_changed.connect(self.set_output_state)


        self.last_few_fps: list[float] = []
        self.last_time = time.perf_counter()
        # start out right size to remove source of startup window jumping
        underscore_str = f"{"_" * len(str(target_fps))}.__"
        self.fps_len = len(underscore_str)
        self.fps_counter = QLabel(f"<code>{underscore_str}/{target_fps}</code> FPS")

        self.paused = False
        self.pause_play_button = PushButton.new("Pause", self.pause_play, tooltip="Shortcut: P")
        self.reset_inputs_button = PushButton.new("Reset inputs", self.reset_inputs, tooltip="Shortcut: R")


        self.frameless_checkbox = make_checkbox("Frameless", self.set_frameless)

        self.on_top_checkbox = make_checkbox("Always on top", self.set_on_top, checked=True)

        if self.is_wayland:
            pseudo_disable(self.on_top_checkbox, tooltip="Your display server (Wayland) ignores this setting and requires you to instead right-click this window's top bar to pin it!", checked=False)


        # TODO: I kinda want an FPS toggle for trivial simulations without
        # clocks, and this is unwieldy already with two options lol
        if show_reset and show_pause:
            self.gui_meta_box = vbox_factory(
                hbox_factory(self.pause_play_button, self.reset_inputs_button),
                hbox_factory(self.fps_counter, self.frameless_checkbox, self.on_top_checkbox)
            )
        elif show_reset:
            self.gui_meta_box = vbox_factory( 
                hbox_factory(self.reset_inputs_button, self.frameless_checkbox),
                hbox_factory(self.fps_counter, self.on_top_checkbox)
            )
        elif show_pause:
            self.gui_meta_box = vbox_factory( 
                hbox_factory(self.pause_play_button, self.frameless_checkbox),
                hbox_factory(self.fps_counter, self.on_top_checkbox)
            )
        else: # both false
            self.gui_meta_box = hbox_factory(self.fps_counter, self.frameless_checkbox, self.on_top_checkbox)
        
        # subclasses put all their widgets in here 
        # Final so type checker prevents shadowing rather than adding
        self.model_interaction_box: Final = vbox_factory()

        self.main_layout.addLayout(self.model_interaction_box)
        self.main_layout.addLayout(self.gui_meta_box)

        # Pause/play with P.
        #   Spacebar is more obvious, but it makes tabbed navigation not work
        self.addAction(make_action("Pause/play", self.pause_play_button.click, "P", self))
        
        if show_reset:
            # Reset inputs with R
            self.addAction(make_action("Reset inputs", self.reset_inputs_button.click, "R", self))

        # Allow quitting with ctrl+W/cmd+W
        self.addAction(make_action("Quit simulation", QApplication.quit, "Ctrl+W", self))

        if fixed_size:
            QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))

        self.checked_init = False
        QTimer.singleShot(0, self.quit_if_not_checked)

    def post_init_check(self):
        self.checked_init = True
        if any(len(d) == 0 for d in [self.input_state, self.output_state]):
            error_quit("Malformed virtual board; must reinitialize input state and output state")
            QTimer.singleShot(0, QApplication.quit)
        else:
            self.latest = self.input_state.copy()
            self.previous = self.latest.copy() # start: previous is 0 too

    def quit_if_not_checked(self):
        if not self.checked_init:
            error_quit(f"Subclass must call {Fore.CYAN}{Style.BRIGHT}post_init_check(){Style.RESET_ALL}")
            QTimer.singleShot(0, QApplication.quit)

    def reset_inputs(self):
        for w in self.input_widgets:
            w.reset_device()

    def pause_play(self):
        self.paused = not self.paused
        if self.paused:
            self.setWindowTitle(f"{self.win_title} (paused)")
            self.pause_play_button.setText("Play")
            self.fps_counter.setText(f"<em><code>&nbsp;PAUSED&nbsp;</code></em> FPS")
            self.last_few_fps.clear() # While paused, times are meaningless
        else:
            self.setWindowTitle(f"{self.win_title} (running)")
            self.pause_play_button.setText("Pause")
            self.last_few_fps.clear()
            self.last_time = time.perf_counter()
            self.input_time.emit()

    
    def update_fps(self):
        new_time = time.perf_counter()
        self.last_few_fps.append(1/(new_time - self.last_time))
        if len(self.last_few_fps) == 10:
            n = mean(self.last_few_fps)
            # format to 2 digits with padding on left to not jump
            nbsp = " " # use NBSP so Qt HTML renderer keeps the spaces
            self.fps_counter.setText(f"<code>{n:{nbsp}>{self.fps_len}.2f}/{self.target_fps}</code> FPS")
            self.last_few_fps.clear()
        self.last_time = new_time

    def update_server(self):
        if not self.paused:
            # only sends the ones that changed
            send_message(str(dict_diff(self.latest, self.previous)), self.sock)
            self.previous.update(self.latest)
        else:
            send_message("", self.sock)


    def update_input_state(self, updates: Mapping[str, int | bool]):
        for key, state in updates.items():
            self.input_state[key] = int(state) # allows bools for flag vars
            self.input_changed.emit(self.input_state)


    def update_latest(self, new_latest: dict):
        self.latest.update(new_latest)


    @Slot(object)
    def set_output_state(self, new_output_state: dict):
        self.output_state.update(new_output_state)
        self.update_display_devices()

    def update_display_devices(self):
        error_quit("Virtual board must override update_display_devices()!")

class ListenThread(QThread):
    def __init__(self, window: BaseGUIWindow):
        super().__init__()
        self.window = window

        self.listener_done = window.listener_done
        self.have_quit = window.have_quit

    @override
    def run(self):
        window = self.window
        sock = window.sock

        # Timer with support for nanosecond precision
        our_timer = QDeadlineTimer()

        while True:
            our_timer.setPreciseRemainingTime(0, nsecs=round(1_000_000_000/window.target_fps))
            window.input_time.emit()
            # response is either exit or a (maybe empty) list of lines printed by the Verilog program
            response = big_receive(sock).decode()
            window.pinged.emit() # update FPS after receiving

            if response == "exit":
                self.listener_done.set()
                break
            else:
                verilog_prints = ast.literal_eval(response)
                if len(verilog_prints) > 0:
                    message = "\n".join([textwrap.indent(s, " " * 4) for s in verilog_prints])
                    print(f"{Fore.BLUE}{Style.BRIGHT}{message}{Style.RESET_ALL}")

                # get the output dict expected after the Verilog list
                output_state = deserialize_dict(big_receive(sock).decode()) # really OutputDict
                if not self.have_quit.is_set(): # make sure to not do Qt stuff if app has quit. (Not sure if necessary)
                    window.output_changed.emit(output_state)

            while not our_timer.hasExpired():
                time.sleep(window.sleep_resolution)

class Runner:
    def __init__(self) -> None:
        if sys.platform != 'win32':
            # reconstruct socket from regular file descriptor
            self.sock = reconstruct_socket_unix(int(sys.argv[2]))
        else: # make socket from received output of socket.share()
            import base64
            socket_share_data = base64.b64decode(sys.stdin.buffer.read())
            self.sock = reconstruct_socket_windows(socket_share_data)

        self.program_name = sys.argv[1]
        self.app = QApplication()
        self.app.setStyle(AppStyle())

    def run(self, c: type[BaseGUIWindow]):
        # make a window. TODO: Runner really doesn't need to be the creator
        #   of the flags, and the parameter situation is wonky.
        #   Only the program name and sock name originate from here.
        #   We DO need to either make the window here, or receive the app as
        #   param 1.
        window = c(self.program_name, self.sock) # pyright: ignore[reportCallIssue]
        # pin to top at start (ignored on Wayland)
        window.set_on_top(True)
        self.app.exec()

        window.have_quit.set()
        send_message("exit", self.sock)
        window.listener_done.wait()
        print("Exited live sim!")