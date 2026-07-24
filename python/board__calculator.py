'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict, override

import gui__constants as c
from board__base import BaseGUIWindow, Runner
from gui__widgets import (
    BoardComponents,
    NormalButton,
    vbox_factory,
)
from PySide6.QtWidgets import QGridLayout, QSizePolicy


class OutputDict(TypedDict, total=True):
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    select: int
    matrix: int

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    b0: int
    b1: int
    b2: int
    b3: int
    b4: int
    b5: int
    b6: int
    b7: int
    b8: int
    b9: int
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
        self.input_state = InputDict(b0=0, b1=0, b2=0, b3=0, b4=0, b5=0, b6=0, b7=0, b8=0, b9=0, equals=0, clear=0, divide=0, multiply=0, subtract=0, add=0)

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
            [self.clr_btn,      self.calc_nums[0], self.eql_btn,      self.add_btn],
        ]

        for row in range(0, 4):
            for col in range(0, 4):
                self.calc_area.addWidget(grid_list[row][col], row + 1, col + 1)
                self.calc_area.setColumnStretch(col, 0)
            self.calc_area.setRowStretch(row, 0)


        self.model_interaction_box.addLayout(
            vbox_factory(
                self.display,
                self.calc_area
            )
        )

        self.post_init_check()

    def make_calc_button(self, label: str, key: str):
        b = NormalButton(label, None, font_points=c.Sizes.calc_button_font, mono=True)
        b.setFixedHeight(c.Sizes.calc_button_height)
        # ignore policy for horizontal makes it minimum (trial and error tbh)
        b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        b.state_changed.connect(lambda s: self.update_input_state({key: int(s)}))
        return b

    @override # mandatory to override this!!!
    def update_display_devices(self):
        self.display.set(self.output_state["matrix"], self.output_state["select"])


if __name__ == "__main__":
    Runner().run(MainWindow)