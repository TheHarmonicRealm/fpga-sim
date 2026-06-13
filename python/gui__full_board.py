'''
Launched as subprocess from client__shell.py
'''

import ast
import base64
import os
import socket
import sys
import threading
import time
from statistics import mean

from colorama import Fore, Style
from gui__widgets import (
    BoardComponents,
    EmptyWindow,
    hbox_factory,
    int_to_bool_list,
    make_app,
    vbox_factory,
)
from PySide6.QtCore import QPoint, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton
from shared__util import big_receive, send_message

msg_dict = dict[str, int]

def deserialize_dict(d: str) -> msg_dict:
    return ast.literal_eval(d)

class MainWindow(EmptyWindow):
    input_changed = Signal(object)
    output_changed = Signal(object)
    pinged = Signal()
    close_signal = Signal()
    def __init__(self, sock: socket.socket):
        super().__init__("FPGA board view")
        self.sock = sock

        self.output_state = {"lights": 0, "anode": 0b1111, "segment": 0b111_111}
        self.input_state = {"UB": 0, "DB": 0, "LB": 0, "RB": 0, "CB": 0, "switches": 0}

        self.plus_buttons = BoardComponents.Buttons(self.shift_pressed)
        self.four_digits = BoardComponents.FourDigits()
        self.lights_line = BoardComponents.Lights()
        self.switches_line = BoardComponents.Switches()

        self.frameless_checkbox = QCheckBox("Frameless")
        self.frameless_checkbox.toggled.connect(self.set_frameless)

        self.on_top_checkbox = QCheckBox("Always on top")
        self.on_top_checkbox.setChecked(True)
        self.on_top_checkbox.toggled.connect(self.set_on_top)

        self.main_layout.addWidget(self.plus_buttons)
        self.main_layout.addWidget(self.four_digits)
        self.main_layout.addLayout(vbox_factory(self.lights_line, self.switches_line))

        self.paused = False

        self.pause_play_button = QPushButton("Pause simulation [P]")
        self.pause_play_button.pressed.connect(self.pause_play)

        self.reset_inputs_button = QPushButton("Reset inputs [R]")
        self.reset_inputs_button.released.connect(self.reset_inputs)

        self.main_layout.addLayout(hbox_factory(self.pause_play_button, self.reset_inputs_button))


        self.switches_line.state_changed.connect(lambda x: self.update_input_state(switches=x))
        self.plus_buttons.state_changed.connect(lambda x: self.update_input_state(buttons=x))

        self.latest: None | msg_dict = None

        self.should_quit = False

        self.input_changed.connect(self.update_latest)
        self.output_changed.connect(self.set_output_state)
        self.close_signal.connect(self.quit_program)

        self.update_timer = QTimer(interval=17)
        self.update_timer.timeout.connect(self.update_server)
        self.update_timer.start()

        self.last_few_fps: list[float] = []
        self.last_time = time.time()
        self.fps_counter = QLabel("__.__/60 FPS")

        if "WAYLAND_DISPLAY" not in os.environ:
            self.main_layout.addLayout(hbox_factory(self.fps_counter, self.frameless_checkbox, self.on_top_checkbox))
        else: # always-on-top not available on Wayland. Instead right-click title bar
            self.main_layout.addLayout(hbox_factory(self.fps_counter, self.frameless_checkbox))

        # Pause/play with P.
        #   Spacebar is more obvious, but it makes tabbed navigation not work
        self.pause_play_action = QAction("Pause/play", self)
        self.pause_play_action.setShortcut(QKeySequence("P"))
        self.pause_play_action.setAutoRepeat(False)
        self.pause_play_action.triggered.connect(self.pause_play_button.click)
        self.addAction(self.pause_play_action)

        # Reset inputs with R
        self.reset_inputs_action = QAction("Reset inputs", self)
        self.reset_inputs_action.setShortcut(QKeySequence("R"))
        self.reset_inputs_action.setAutoRepeat(False)
        self.reset_inputs_action.triggered.connect(self.reset_inputs_button.click)
        self.addAction(self.reset_inputs_action)

        self.ctrl_w_quit = QAction("Quit simulation", self)
        self.ctrl_w_quit.setShortcut(QKeySequence("Ctrl+W"))
        self.ctrl_w_quit.setAutoRepeat(False)
        self.ctrl_w_quit.triggered.connect(QApplication.quit)
        self.addAction(self.ctrl_w_quit)

        self.pinged.connect(self.update_fps)

        t = threading.Thread(target=lambda: listen(self), daemon=True)
        t.start()

        QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))
    
    def reset_inputs(self):
        for button in self.plus_buttons.buttons_list:
            button.setChecked(False)
        for switch in self.switches_line.checkboxes:
            switch.setChecked(False)

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
    def set_output_state(self, new_output_state: msg_dict):
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
        new_time = time.time()
        self.last_few_fps.append(1/(new_time - self.last_time))
        if len(self.last_few_fps) == 10:
            self.fps_counter.setText(f"<code>{mean(self.last_few_fps):.2f}/60</code> FPS")
            self.last_few_fps.clear()
        self.last_time = new_time


    def update_server(self):
        if not self.paused:
            if self.latest is not None:
                send_message(str(self.latest), self.sock)
                self.latest = None
            else:
                send_message("", self.sock)


    def update_latest(self, new_latest: msg_dict):
        self.latest = new_latest

    def pause_play(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_play_button.setText("Play")
            self.fps_counter.setText(f"<em><code>&nbsp;PAUSED&nbsp;</code></em> FPS")
            self.last_few_fps.clear() # While paused, times are meaningless
            self.last_time = time.time()
        else:
            self.pause_play_button.setText("Pause")


def listen(window: MainWindow):
    global listener_done
    global have_quit
    sock = window.sock
    while True:
        response = big_receive(sock).decode()

        # update FPS count
        window.pinged.emit()

        # quitting app sends an exit signal then server replies with exit
        if response == "exit":
            listener_done.set()
            break
        else: # hasn't given exit response: continue as normal for a frame or so
            output_state = deserialize_dict(response)
            if not have_quit.is_set(): # make sure to not do Qt stuff if app has quit. (Not sure if necessary)
                window.output_changed.emit(output_state)

def run_app(sock: socket.socket):
    app = make_app()
    window = MainWindow(sock)
    # hacky way to make sure it starts on top
    # TODO: do it without needing to this
    window.set_on_top(True)
    window.show()
    app.exec()
    return app

if __name__ == "__main__":
    listener_done = threading.Event()
    have_quit = threading.Event()

    if sys.platform != 'win32':
        # reconstruct socket from regular file descriptor
        try:
            sock_fd = int(sys.argv[1])
            sock = socket.fromfd(sock_fd, socket.AF_INET, socket.SOCK_STREAM)
        except OSError, IndexError:
            # TODO: make names more logical
            print("Don't run gui__main directly!! Run client__shell")
            exit(1)
    else: # make socket from received output of socket.share()
        windows_socket = base64.b64decode(sys.stdin.buffer.read())
        sock = socket.fromshare(windows_socket)

    run_app(sock)

    # app has been quit. tell server we are quitting then wait for
    #   listener to get ACK back. Necessary to have a "clean" socket on exit
    #   for main program to continue with as normal
    have_quit.set()
    send_message("exit", sock)
    listener_done.wait()
    print("Exited live sim!")