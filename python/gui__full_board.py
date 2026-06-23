'''
Launched as subprocess from client__shell.py
'''

import base64
import socket
import sys
import threading
from typing import TypedDict

from colorama import Fore, Style
from gui__base import BaseGUIWindow
from gui__util import reconstruct_socket_unix, reconstruct_socket_windows
from gui__widgets import (
    BoardComponents,
    int_to_bool_list,
    make_action,
    make_app,
    make_button,
    pseudo_disable,
    vbox_factory,
)
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QApplication
from shared__util import dict_diff, send_message


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    lights: int
    DP: int
    anode: int
    segment: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    UB: int
    DB: int
    LB: int
    RB: int
    CB: int
    switches: int

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket, listener_done: threading.Event, have_quit: threading.Event):
        super().__init__(f"\"{program_name}\" running on classic devkit", sock, listener_done, have_quit)

        self.output_state = OutputDict(lights=0, DP=0b1, anode=0b1111, segment=0b111_111)
        self.input_state = InputDict(UB=0, DB=0, LB=0, RB=0, CB=0, switches=0)

        self.plus_buttons = BoardComponents.Buttons(self.shift_pressed)
        self.four_digits = BoardComponents.FourDigits()
        self.lights_line = BoardComponents.Lights()
        self.switches_line = BoardComponents.Switches()

        self.input_widgets += [self.plus_buttons, self.switches_line]

        if not self.is_wayland:
            pseudo_disable(self.on_top_checkbox, tooltip="Your display server (Wayland) ignores this setting and requires you to instead right-click this window's top bar to pin it!", checked=False)

        self.pause_play_button = make_button("Pause simulation", self.pause_play, tooltip="Shortcut: P")
        self.reset_inputs_button = make_button("Reset inputs", self.reset_inputs, tooltip="Shortcut: R")

        self.paused = False

        self.switches_line.state_changed.connect(lambda x: self.update_input_state(switches=x))
        self.plus_buttons.state_changed.connect(lambda x: self.update_input_state(buttons=x))

        self.latest = self.input_state.copy()
        self.previous = self.latest.copy() # start: previous is 0 too

        self.should_quit = False

        self.input_changed.connect(self.update_latest)
        self.output_changed.connect(self.set_output_state)
        self.close_signal.connect(self.quit_program)

        self.model_interaction_box.addLayout(
            vbox_factory(
                self.plus_buttons,
                self.four_digits,
                self.lights_line,
                self.switches_line,
            )
        )

        # Pause/play with P.
        #   Spacebar is more obvious, but it makes tabbed navigation not work
        self.addAction(make_action("Pause/play", self.pause_play_button.click, "P", self))
        
        # Reset inputs with R
        self.addAction(make_action("Reset inputs", self.reset_inputs_button.click, "R", self))

        # Allow quitting with ctrl+W/cmd+W
        self.addAction(make_action("Quit simulation", QApplication.quit, "Ctrl+W", self))

        self.pinged.connect(self.update_fps)
        self.input_time.connect(self.update_server)

        QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))

    @Slot(object)
    def set_output_state(self, new_output_state: OutputDict):
        # NOTE: if new_output_state adds keys or is missing some will not error
        # Must become job of another component program to verify that the
        # Verilog program's ports match the GUI program's ports
        self.output_state.update(new_output_state)
        try:
            self.lights_line.set_output_state(self.output_state["lights"])
            self.four_digits.set(self.output_state["segment"], self.output_state["DP"], self.output_state["anode"])
        except KeyError: # NOTE: see above... this will never happen currently
            print("Error: your verilog code's inputs and/or outputs did not match the required format for the \"classic\" board.")
            print(f"Please refer to the template at {Fore.CYAN}{Style.BRIGHT}./templates/classic.v{Style.RESET_ALL} if this is the board you meant to use.")
             # TODO: do this in a smarter way, matching sizes too,
             # and find a way to also match port widths
            QApplication.quit()

    def update_input_state(self, *, buttons: int | None = None, switches: int | None = None):
        if buttons is not None:
            for b, state in zip(["UB", "DB", "LB", "RB", "CB"], int_to_bool_list(buttons, 5)):
                self.input_state[b] = int(state)
        if switches is not None:
            self.input_state["switches"] = switches
        self.input_changed.emit(self.input_state)
    
    def ready_quit(self):
        self.should_quit = True

    @Slot()
    def quit_program(self):
        # get app instance, then close window before quitting app
        app: QApplication = QApplication.instance() # pyright: ignore[reportAssignmentType]
        self.close()
        app.exit()


    def update_server(self):
        if not self.paused:
            # only sends the ones that changed
            send_message(str(dict_diff(self.latest, self.previous)), self.sock)
            self.previous.update(self.latest)
        else:
            send_message("", self.sock)


    def update_latest(self, new_latest: InputDict):
        self.latest.update(new_latest)


def run_app(program_name: str, sock: socket.socket, listener_done: threading.Event, have_quit: threading.Event):
    app = make_app()
    window = MainWindow(program_name, sock, listener_done, have_quit)
    # pin to top at start (ignored on Wayland)
    window.set_on_top(True)
    app.exec()
    return app

if __name__ == "__main__":
    listener_done = threading.Event()
    have_quit = threading.Event()

    if sys.platform != 'win32':
        # reconstruct socket from regular file descriptor
        sock = reconstruct_socket_unix(int(sys.argv[2]))
    else: # make socket from received output of socket.share()
        socket_share_data = base64.b64decode(sys.stdin.buffer.read())
        sock = reconstruct_socket_windows(socket_share_data)

    program_name = sys.argv[1]

    run_app(program_name, sock, listener_done, have_quit)

    # app has been quit. tell server we are quitting then wait for
    #   listener to get ACK back. Necessary to have a "clean" socket on exit
    #   for main program to continue with as normal
    have_quit.set()
    send_message("exit", sock)
    listener_done.wait()
    print("Exited live sim!")