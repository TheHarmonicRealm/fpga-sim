'''
Launched as subprocess from client__shell.py
'''

import ast
import base64
import os
import socket
import sys
import textwrap
import threading
import time
from statistics import mean
from typing import TypedDict

from colorama import Fore, Style
from gui__util import reconstruct_socket_unix, reconstruct_socket_windows
from gui__widgets import (
    BoardComponents,
    EmptyWindow,
    InputWidget,
    hbox_factory,
    int_to_bool_list,
    make_action,
    make_app,
    make_button,
    make_checkbox,
    pseudo_disable,
    vbox_factory,
)
from PySide6.QtCore import QDeadlineTimer, QPoint, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QLabel
from shared__util import big_receive, dict_diff, send_message


class OutputDict(TypedDict):
    lights: int
    DP: int
    anode: int
    segment: int

class InputDict(TypedDict):
    UB: int
    DB: int
    LB: int
    RB: int
    CB: int
    switches: int

def deserialize_dict(d: str) -> dict:
    return ast.literal_eval(d)

class MainWindow(EmptyWindow):
    input_changed = Signal(InputDict)
    output_changed = Signal(OutputDict)
    input_time = Signal()
    pinged = Signal()
    close_signal = Signal()
    def __init__(self, sock: socket.socket):
        super().__init__("FPGA board view")
        self.sock = sock

        self.output_state: OutputDict = {"lights": 0, "DP": 0b1, "anode": 0b1111, "segment": 0b111_111}
        self.input_state: InputDict = {"UB": 0, "DB": 0, "LB": 0, "RB": 0, "CB": 0, "switches": 0}

        self.plus_buttons = BoardComponents.Buttons(self.shift_pressed)
        self.four_digits = BoardComponents.FourDigits()
        self.lights_line = BoardComponents.Lights()
        self.switches_line = BoardComponents.Switches()

        self.input_widgets: list[InputWidget] = [self.plus_buttons, self.switches_line]

        # TODO: style tooltips; seems to be stylesheets-managed
        self.frameless_checkbox = make_checkbox("Frameless", self.set_frameless)

        self.on_top_checkbox = make_checkbox("Always on top", self.set_on_top, checked=True)

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

        self.last_few_fps: list[float] = []
        self.last_time = time.perf_counter()
        self.fps_counter = QLabel("__.__/60 FPS")


        model_interaction_box = vbox_factory(
            self.plus_buttons,
            self.four_digits,
            self.lights_line, self.switches_line
        )

        # contains: pause, input reset, window settings, and FPS counter
        gui_meta_box = vbox_factory(
            hbox_factory(self.pause_play_button, self.reset_inputs_button),
            hbox_factory(self.fps_counter, self.frameless_checkbox, self.on_top_checkbox)
        )

        self.main_layout.addLayout(model_interaction_box)
        self.main_layout.addLayout(gui_meta_box)

        # Pause/play with P.
        #   Spacebar is more obvious, but it makes tabbed navigation not work
        self.addAction(make_action("Pause/play", self.pause_play_button.click, "P", self))
        
        # Reset inputs with R
        self.addAction(make_action("Reset inputs", self.reset_inputs_button.click, "R", self))

        # Allow quitting with ctrl+W/cmd+W
        self.addAction(make_action("Quit simulation", QApplication.quit, "Ctrl+W", self))

        self.pinged.connect(self.update_fps)
        self.input_time.connect(self.update_server)

        # important: put thread under self or gc destroys it immediately
        self.t = ListenThread(window=self)
        self.t.start()

        QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))
    
    def reset_inputs(self):
        for w in self.input_widgets:
            w.reset_device()

    def set_frameless(self, enable: bool):
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, enable)

        if sys.platform == 'win32':
            if not enable:
                # nudge a tiny bit to fix issue where size is wrong after
                #   made frameful, then wait a tiny bit before going home
                target_pos = self.pos() - QPoint(0, 30) 
                QTimer.singleShot(0, lambda: self.move(self.pos() + QPoint(1, 0)))
                QTimer.singleShot(50, lambda: self.move(target_pos))
            else: # move down by size of top bar
                QTimer.singleShot(0, lambda: self.move(self.pos() + QPoint(0, 30)))
        elif sys.platform == 'darwin':
            if enable:
                self.move(self.pos() + QPoint(0, 28))
            else:
                self.move(self.pos() + QPoint(0, -28))
        self.show()

    def set_on_top(self, enable: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enable)
        self.show()

    @Slot(object)
    def set_output_state(self, new_output_state: OutputDict):
        try:
            self.lights_line.set_output_state(new_output_state["lights"])
            self.four_digits.set(new_output_state["segment"], new_output_state["DP"], new_output_state["anode"])
        except KeyError:
            print("Error: your verilog code's inputs and/or outputs did not match the required format for the \"classic\" board.")
            print(f"Please refer to the template at {Fore.CYAN}{Style.BRIGHT}./templates/classic.v{Style.RESET_ALL} if this is the board you meant to use.")
             # TODO: do this in a smarter way, matching sizes too,
             # and find a way to also match port widths
            QApplication.quit()
        self.output_state.update(new_output_state)

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

    def update_fps(self):
        new_time = time.perf_counter()
        self.last_few_fps.append(1/(new_time - self.last_time))
        if len(self.last_few_fps) == 10:
            self.fps_counter.setText(f"<code>{mean(self.last_few_fps):.2f}/60</code> FPS")
            self.last_few_fps.clear()
        self.last_time = new_time


    def update_server(self):
        if not self.paused:
            # only sends the ones that changed
            send_message(str(dict_diff(self.latest, self.previous)), self.sock)
            self.previous.update(self.latest)
        else:
            send_message("", self.sock)


    def update_latest(self, new_latest: InputDict):
        self.latest.update(new_latest)

    def pause_play(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_play_button.setText("Play")
            self.fps_counter.setText(f"<em><code>&nbsp;PAUSED&nbsp;</code></em> FPS")
            self.last_few_fps.clear() # While paused, times are meaningless
        else:
            self.pause_play_button.setText("Pause")
            self.last_few_fps.clear()
            self.last_time = time.perf_counter()
            self.input_time.emit()


class ListenThread(QThread):
    
    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.window = window

    def run(self):
        window = self.window
        sock = window.sock

        # Timer with support for nanosecond precision
        our_timer = QDeadlineTimer()

        while True:
            our_timer.setPreciseRemainingTime(0, nsecs=round(1_000_000_000/60))
            window.input_time.emit()
            response = big_receive(sock).decode()
            window.pinged.emit()

            # quitting app sends an exit signal then server replies with exit
            if response == "exit":
                listener_done.set()
                break
            else: # hasn't given exit response: continue as normal for a frame or so
                verilog_prints = ast.literal_eval(response)
                if len(verilog_prints) > 0:
                    message = "\n".join([textwrap.indent(s, " " * 4) for s in verilog_prints])
                    print(f"{Fore.BLUE}{Style.BRIGHT}{message}{Style.RESET_ALL}")

                
                response_part_2 = big_receive(sock).decode()
                output_state: OutputDict = deserialize_dict(response_part_2) # pyright: ignore[reportAssignmentType]
                if not have_quit.is_set(): # make sure to not do Qt stuff if app has quit. (Not sure if necessary)
                    window.output_changed.emit(output_state)

            while not our_timer.hasExpired():
                time.sleep(.0005)


def run_app(sock: socket.socket):
    app = make_app()
    window = MainWindow(sock)
    # pin to top at start (ignored on Wayland)
    window.set_on_top(True)
    app.exec()
    return app

if __name__ == "__main__":
    listener_done = threading.Event()
    have_quit = threading.Event()

    if sys.platform != 'win32':
        # reconstruct socket from regular file descriptor
        sock = reconstruct_socket_unix(int(sys.argv[1]))
    else: # make socket from received output of socket.share()
        socket_share_data = base64.b64decode(sys.stdin.buffer.read())
        sock = reconstruct_socket_windows(socket_share_data)

    run_app(sock)

    # app has been quit. tell server we are quitting then wait for
    #   listener to get ACK back. Necessary to have a "clean" socket on exit
    #   for main program to continue with as normal
    have_quit.set()
    send_message("exit", sock)
    listener_done.wait()
    print("Exited live sim!")