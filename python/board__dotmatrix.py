'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict, override


from board__base import BaseGUIWindow, Runner
from gui__widgets import (
    PlusButtons,
    DotMatrixGroup,
    BoardLightsArray,
    BoardSwitchesArray,
    int_to_bool_list,
    hbox_factory,
)

from qt_helpers import vbox_factory, hbox_factory


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    select: int
    matrix: int
    lights: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    UB: int
    DB: int
    LB: int
    RB: int
    CB: int
    switches: int

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket):
        super().__init__(sock, program_name, "dotmatrix", show_reset = True, target_fps=120, sleep_resolution=.00005)

        self.output_state = OutputDict(matrix=0, select=0, lights=0)
        self.input_state = InputDict(UB=0, DB=0, LB=0, RB=0, CB=0, switches=0)

        self.plus_buttons = PlusButtons(self.shift_pressed)
        self.four_digits = DotMatrixGroup(4, 3, 7)
        self.lights_line = BoardLightsArray(16)
        self.switches_line = BoardSwitchesArray(16)

        self.input_widgets += [self.plus_buttons, self.switches_line]

        self.switches_line.state_changed.connect(lambda x: self.update_input_state({"switches": x}))
        self.plus_buttons.state_changed.connect(lambda x: self.update_input_state(dict(zip(["UB", "DB", "LB", "RB", "CB"], int_to_bool_list(x, 5)))))

        self.model_interaction_box.addLayout(
            vbox_factory(
                hbox_factory(self.plus_buttons, self.four_digits),
                self.lights_line,
                self.switches_line,
                
            )
        )

        self.post_init_check()

    @override # mandatory to override this!!!
    def update_display_devices(self):
        self.lights_line.set_output_state(self.output_state["lights"])
        self.four_digits.set(self.output_state["matrix"], self.output_state["select"])



if __name__ == "__main__":
    Runner().run(MainWindow)