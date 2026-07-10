'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict

import gui__constants as c
from gui__base import BaseGUIWindow, Runner
from gui__widgets import (
    BoardComponents,
    NormalButton,
    vbox_factory,
)
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QGridLayout, QSizePolicy
from shared__util import dict_diff, send_message


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    select: int
    matrix: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    B0: int
    B1: int
    B2: int
    B3: int
    B4: int
    B5: int
    B6: int
    B7: int
    B8: int
    B9: int
    equals: int
    clear: int
    divide: int
    multiply: int
    subtract: int
    add: int

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket):
        super().__init__(sock, program_name, "calculator", show_reset = False, target_fps=120, sleep_resolution=.00005)

        self.output_state = OutputDict(matrix=0, select=0)
        self.input_state = InputDict(B0 = 0, B1 = 0, B2 = 0, B3 = 0, B4 = 0, B5 = 0, B6 = 0, B7 = 0, B8 = 0, B9 = 0, equals = 0, clear = 0, divide = 0, multiply = 0, subtract = 0, add = 0)

        self.display = BoardComponents.DotMatrixGroup(4, 3, 5, inter_spacing=6)

        self.calc_area = QGridLayout()
        self.calc_area.setSpacing(1)

        self.calc_nums = [self.make_calc_button(f"{num}", f"b{num}") for num in range(0, 10)]
        
        self.eql_btn = self.make_calc_button("=", "equals")
        self.clr_btn = self.make_calc_button("c", "clear")
        self.div_btn = self.make_calc_button("÷", "divide")
        self.mul_btn = self.make_calc_button("×", "multiply")
        self.sub_btn = self.make_calc_button("-", "subtract")
        self.add_btn = self.make_calc_button("+", "add")

        grid_list = [
            [self.calc_nums[7], self.calc_nums[8], self.calc_nums[9], self.div_btn],
            [self.calc_nums[4], self.calc_nums[5], self.calc_nums[6], self.mul_btn],
            [self.calc_nums[1], self.calc_nums[2], self.calc_nums[3], self.sub_btn],
            [self.clr_btn,           self.calc_nums[0], self.eql_btn,           self.add_btn],
        ]

        for row in range(0, 4):
            for col in range(0, 4):
                self.calc_area.addWidget(grid_list[row][col], row + 1, col + 1)
                self.calc_area.setColumnStretch(col, 0)
            self.calc_area.setRowStretch(row, 0)

        self.latest = self.input_state.copy()
        self.previous = self.latest.copy() # start: previous is 0 too

        self.should_quit = False

        self.input_changed.connect(self.update_latest)
        self.output_changed.connect(self.set_output_state)

        self.model_interaction_box.addLayout(
            vbox_factory(
                self.display,
                self.calc_area
                
            )
        )

        self.pinged.connect(self.update_fps)
        self.input_time.connect(self.update_server)

        QTimer.singleShot(0, lambda: self.setFixedSize(self.minimumSizeHint()))

    def make_calc_button(self, label: str, key: str):
        b = NormalButton(label, None, font_points=c.Sizes.calc_button_font, mono=True)
        b.setFixedHeight(c.Sizes.calc_button_height)
        # ignore policy for horizontal makes it minimum (trial and error tbh)
        b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        b.state_changed.connect(lambda s: self.update_input_state(key, int(s)))
        return b

    @Slot(object)
    def set_output_state(self, new_output_state: OutputDict):
        self.output_state.update(new_output_state)
        self.display.set(self.output_state["matrix"], self.output_state["select"])

    def update_input_state(self, key: str, state: int):
        self.input_state[key] = state
        self.input_changed.emit(self.input_state)
    
    def ready_quit(self):
        self.should_quit = True

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