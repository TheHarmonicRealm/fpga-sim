'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict, override

from board__base import BaseGUIWindow, Runner
from qt_helpers import hbox_factory, vbox_factory
from gui__widgets import BoardLightsArray, BoardSwitchesArray


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    lights: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    switches: int

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket):
        super().__init__(sock, program_name, "switches", show_reset = True, target_fps=120, sleep_resolution=.00005)

        self.output_state = OutputDict(lights=0)
        self.input_state = InputDict(switches=0)

        self.lights_line = BoardLightsArray(16)
        self.switches_line = BoardSwitchesArray(16)

        self.input_widgets += [self.switches_line]

        self.switches_line.state_changed.connect(lambda x: self.update_input_state({"switches": x}))

        self.model_interaction_box.addLayout(
            vbox_factory(
                self.lights_line,
                self.switches_line,
            )
        )

        self.post_init_check()

    @override # mandatory to override this!!!
    def update_display_devices(self):
        self.lights_line.set_output_state(self.output_state["lights"])


if __name__ == "__main__":
    Runner().run(MainWindow)