'''
Launched as subprocess from client__shell.py
'''

import socket
import threading
from typing import TypedDict

from gui__base import BaseGUIWindow, Runner
from gui__widgets import (
    BoardComponents,
    vbox_factory,
)
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QApplication
from shared__util import dict_diff, send_message


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    lights: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    switches: int

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket, listener_done: threading.Event, have_quit: threading.Event):
        super().__init__(sock, listener_done, have_quit, program_name, "switches", show_pause=False, show_reset=False)

        self.output_state = OutputDict(lights=0)
        self.input_state = InputDict(switches=0)

        self.lights_line = BoardComponents.Lights()
        self.switches_line = BoardComponents.Switches()

        self.input_widgets += [self.switches_line]

        self.switches_line.state_changed.connect(lambda x: self.update_input_state(switches=x))

        self.latest = self.input_state.copy()
        self.previous = self.latest.copy() # start: previous is 0 too

        self.should_quit = False

        self.input_changed.connect(self.update_latest)
        self.output_changed.connect(self.set_output_state)
        self.close_signal.connect(self.quit_program)

        self.model_interaction_box.addLayout(
            vbox_factory(
                self.lights_line,
                self.switches_line,
            )
        )

        self.pinged.connect(self.update_fps)
        self.input_time.connect(self.update_server)

        QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))
        # TODO: don't feel like adding this option to gui__base rn but should
        QTimer.singleShot(0, lambda: self.fps_counter.hide())

    @Slot(object)
    def set_output_state(self, new_output_state: OutputDict):
        self.output_state.update(new_output_state)
        self.lights_line.set_output_state(self.output_state["lights"])

    def update_input_state(self, *, switches: int | None = None):
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

if __name__ == "__main__":
    r = Runner()
    r.run(MainWindow)