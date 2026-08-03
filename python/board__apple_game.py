'''
Launched as subprocess from client__shell.py
'''

import re
import socket
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict, override

import gui__constants as c
from board__base import BaseGUIWindow, Runner
from client__paths import apple_game_svg
from gui__widgets import (
    BoardButton,
    BoardLight,
    DotMatrixGroup,
    hbox_factory,
    vbox_factory,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtSvgWidgets import QSvgWidget
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

class HideySVG:
    def __init__(self, svg_path: Path) -> None:
        svg_string = svg_path.read_text()

        # take xlmns out, if present, before parsing
        search_xmlns = re.search(r'xmlns="(.*)"', svg_string)
        if search_xmlns is not None:
            xmlns_version: str | None = search_xmlns.group(1)
            svg_string = re.sub(f'xmlns="{xmlns_version}"', "", svg_string)
        else:
            xmlns_version = None

        self.root = ET.fromstring(svg_string)

        # restore xlmns if it was present
        if xmlns_version is not None:
            self.root.attrib["xlmns"] = xmlns_version

    def get_string(self):
        return ET.tostring(self.root, encoding='unicode')

    def set_element_visibility(self, id: str, show: bool):
        node = self.root.find(f".//*[@id='{id}']")
        if node is None:
            raise ValueError(f'No element with id "{id}"!')
        else:
            if show:
                node.attrib["display"] = "inline"
            else:
                node.attrib["display"] = "none"
            return ET.tostring(self.root, encoding='unicode')

class SVGRenderer(QSvgWidget):
    def __init__(self, svg_path: Path, state_dict: dict[str, bool], size: tuple[int, int]) -> None:
        super().__init__()

        self.our_svg = HideySVG(svg_path)

        self.state_dict = state_dict
        for id in self.state_dict:
            self.our_svg.set_element_visibility(id, False)

        self.refresh_image()
        self.setFixedSize(*size)

        self.LR = ["left", "right"]
        self.LCR = ["left", "center", "right"]

    def refresh_image(self):
        svg_bytes = bytearray(self.our_svg.get_string(), encoding='utf-8')
        self.renderer().load(svg_bytes)

    def conv_dict(self, d: dict[str, int]):
        raise NotImplementedError(f"{self.__qualname__} must override method conv_dict() of SVGRenderer!")

    def set(self, d: dict[str, int]):
        changes = dict_diff(self.conv_dict(d), self.state_dict)

        if len(changes) > 0:
            for key, val in changes.items():
                self.our_svg.set_element_visibility(key, val)

            self.state_dict.update(changes)

            self.refresh_image()

class GWRenderer(SVGRenderer):
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
            self.gw_renderer = GWRenderer()
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