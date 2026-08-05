'''
Launched as subprocess from client__shell.py
'''

import socket
from typing import TypedDict, override

import gui__constants as c
from board__base import BaseGUIWindow, Runner
from client__paths import apple_game_svg
from gui__widgets import (
    BoardButton,
    BoardLight,
    DotMatrixGroup,
    SVGRenderer,
    hbox_factory,
    vbox_factory,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QSizePolicy, QSpacerItem, QWidget
from shared__util import dict_diff, int_to_bool_list


class OutputDict(TypedDict, total=True): #[str, int]
    # it doesn't need to be total but you can't mark a specific instance as
    # total so this lies to the type checker to make set_output_state not busy
    apple_spawn_row: int # 2-bit
    apple_left_col: int # 3-bit
    apple_center_col: int # 3-bit
    apple_right_col: int # 3-bit
    basket: int # 3-bit
    oof: int # 3-bit
    score_select: int # 2-bit
    score_pattern: int # 15-bit
    high_select: int # 2-bit
    high_pattern: int # 15-bit

class InputDict(TypedDict, total=False):
    # non-total to allow sending just diffs up
    left: int
    right: int
    restart: int

class GameRenderer(SVGRenderer):
    def __init__(self) -> None:

        state_dict = {
            "apple-left-0": False,
            "apple-left-1": False,
            "apple-left-2": False,
            "apple-right-0": False,
            "apple-right-1": False,
            "apple-right-2": False,
            "apple-center-0": False,
            "apple-center-1": False,
            "apple-center-2": False,
            "basket-left": False,
            "basket-center": False,
            "basket-right": False,
            "apple-spawn-left": False,
            "apple-spawn-right": False,
            "oof-left": False,
            "oof-center": False,
            "oof-right": False
        }
        super().__init__(apple_game_svg, state_dict, (400, 300))

    @override
    def conv_dict(self, d: OutputDict): # type: ignore
        converted_dict: dict[str, bool] = {}
        converted_dict |= dict(zip([f"apple-spawn-{d}" for d in self.LR], int_to_bool_list(d["apple_spawn_row"], 2)))
        converted_dict |= dict(zip([f"apple-left-{n}" for n in range(0, 3)], int_to_bool_list(d["apple_left_col"], 3)))
        converted_dict |= dict(zip([f"apple-center-{n}" for n in range(0, 3)], int_to_bool_list(d["apple_center_col"], 3)))
        converted_dict |= dict(zip([f"apple-right-{n}" for n in range(0, 3)], int_to_bool_list(d["apple_right_col"], 3)))
        converted_dict |= dict(zip([f"basket-{d}" for d in self.LCR], int_to_bool_list(d["basket"], 3)))
        converted_dict |= dict(zip([f"oof-{d}" for d in self.LCR], int_to_bool_list(d["oof"], 3)))
        return converted_dict

class MainWindow(BaseGUIWindow):
    def __init__(self, program_name: str, sock: socket.socket):
        super().__init__(sock, program_name, "apple game", show_reset = False, target_fps=120, sleep_resolution=.00005, fixed_size=True)

        self.output_state = OutputDict(apple_spawn_row=0, apple_left_col=0, apple_center_col=0, apple_right_col=0, basket=0, oof=0, score_select=0, score_pattern=0, high_select=0, high_pattern=0)
        self.input_state = InputDict(left=0, right=0, restart=0)

        self.alarm_light = BoardLight()

        self.left_button = BoardButton("←", None, font_points=c.Sizes.calc_button_font)
        self.right_button = BoardButton("→", None, font_points=c.Sizes.calc_button_font)
        self.restart_button = BoardButton("Start", None,  font_points=20, mono=False)

        self.left_button.setFixedSize(c.Sizes.calc_button_height, c.Sizes.calc_button_height)
        self.right_button.setFixedSize(c.Sizes.calc_button_height, c.Sizes.calc_button_height)

        self.left_button.state_changed.connect(lambda x: self.update_input_state({"left": x}))
        self.right_button.state_changed.connect(lambda x: self.update_input_state({"right": x}))
        self.restart_button.state_changed.connect(lambda x: self.update_input_state({"restart": x}))

        self.input_widgets += [self.left_button, self.restart_button, self.right_button]


        self.high_score_display = DotMatrixGroup(2, light_size=c.Sizes.mini_dotmatrix_light, intra_spacing=0, inter_spacing=8)
        self.current_score_display = DotMatrixGroup(2, light_size=c.Sizes.mini_dotmatrix_light, intra_spacing=0, inter_spacing=8)

        controls_box = hbox_factory()
        controls_box.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))
        controls_box.addLayout(hbox_factory(self.left_button, self.right_button))
        controls_box.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))


        s_disp = hbox_factory(self.high_score_display, self.current_score_display)

        # give a black background to the wrapper of the two scores
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, c.Colors.DotMatrix.background)
        w = QWidget()
        w.setPalette(pal)
        w.setAutoFillBackground(True)
        w.setLayout(s_disp)

        try:
            self.gw_renderer = GameRenderer()
            self.model_interaction_box.addLayout(
                vbox_factory(
                    self.gw_renderer,
                    controls_box,
                    hbox_factory(w, self.restart_button),
                )
            )
        except Exception as e:
            print("Error making renderer:", e)
            QTimer.singleShot(0, QApplication.quit)

        self.post_init_check()

    @override # mandatory to override this!!!
    def update_display_devices(self):
        self.gw_renderer.set(self.output_state) # pyright: ignore[reportArgumentType]
        self.high_score_display.set(self.output_state["high_pattern"], self.output_state["high_select"])
        self.current_score_display.set(self.output_state["score_pattern"], self.output_state["score_select"])

if __name__ == "__main__":
    Runner().run(MainWindow)