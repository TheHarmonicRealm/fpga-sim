'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict, override


from gui__base import BaseGUIWindow, Runner
from gui__widgets import (
    BoardComponents,
    int_to_bool_list,
    hbox_factory,
    vbox_factory,
)


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    lights: int
    dp: int
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
    def __init__(self, program_name: str, sock: socket.socket):
        super().__init__(sock, program_name, "classic", show_reset = True, target_fps=120, sleep_resolution=.00005)

        self.output_state = OutputDict(lights=0, dp=0b1, anode=0b1111, segment=0b111_111)
        self.input_state = InputDict(UB=0, DB=0, LB=0, RB=0, CB=0, switches=0)

        self.plus_buttons = BoardComponents.Buttons(self.shift_pressed)
        self.four_digits = BoardComponents.FourDigits()
        self.lights_line = BoardComponents.Lights()
        self.switches_line = BoardComponents.Switches()

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
        self.four_digits.set(self.output_state["segment"], self.output_state["dp"], self.output_state["anode"])


if __name__ == "__main__":
    Runner().run(MainWindow)