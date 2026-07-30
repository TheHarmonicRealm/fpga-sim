import threading

from enum import Enum, auto
from typing import override

import gui__constants as c
from PySide6.QtCore import (
    Property,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLayout,
    QProxyStyle,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QStyleOption,
    QWidget,
)
from qt_helpers import PushButton, hbox_factory, vbox_factory
from shared__util import bool_list_to_int, int_to_bool_list


class BoardInput:
    '''Simple superclass for widgets that can be added to a virtual board, 
    currently just to make the "reset inputs" button easily work.'''

    # @abstractmethod
    def reset_device(self) -> None:
        raise NotImplementedError(f"{self.__qualname__} must override method reset_device() of InputDevice!")

class BoardButton(PushButton, BoardInput):
    '''Individual non-sticky button that can have text and a set size.'''
    state_changed = Signal(bool)
    def __init__(self, label: str = "", size: QSize | None = c.Sizes.light, font_points: float | int | None = None, mono: bool = True):

        super().__init__(label)

        if size is not None:
            self.setFixedSize(size)

        self.setMinimumSize(0,0)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        if mono:
            new_font = QFont(["Cascadia Mono", "Menlo", "Consolas", "Lucida Console"])
            new_font.setStyleHint(QFont.StyleHint.Monospace)
        else:
            new_font = self.font()

        if font_points is not None:
            new_font.setPointSizeF(float(font_points))
        self.setFont(new_font)

        self.pressed.connect(lambda: self.state_changed.emit(True))
        self.released.connect(lambda: self.state_changed.emit(False))
    
    @override
    def reset_device(self):
        pass # can't hold down so nothing to do

class StickyButton(QPushButton, BoardInput):
    '''Button with somewhat custom style that stays down if shift is held when
    released. Style is overridden in AppStyle, mainly because the default's
    state is quite hard to read in dark mode on both Mac and Windows 11.'''

    # TODO: rewrite click logic — it is not quite matched to expected behavior.
    #   for example, if you click while it is checked and drag the mouse off
    #   before releasing, it will unexpectedly uncheck.
    state_changed = Signal(bool)
    def __init__(self, shift_pressed: threading.Event, size: QSize = c.Sizes.light):
        super().__init__()
        self.setFixedSize(size)
        self.setCheckable(True)
        self.shift_pressed = shift_pressed

        self.released.connect(self.maybe_uncheck)
        self.pressed.connect(self.handle_press_emit)
        self.toggled.connect(self.handle_release_emit)

    def handle_press_emit(self):
        if not self.isChecked():
            self.state_changed.emit(True)

    def handle_release_emit(self, now_checked: bool):
        if not now_checked:
            self.state_changed.emit(False)
    
    def maybe_uncheck(self):
        if self.isChecked() and not self.shift_pressed.is_set():
            self.setChecked(False)

    @override
    def reset_device(self):
        self.setChecked(False)


class BoardSwitch(QCheckBox, BoardInput):
    '''Checkbox that has the appearance of a vertical on/off switch, if
    style is applied'''
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(c.Sizes.switch)

    @override
    def reset_device(self):
        self.setChecked(False)


class BoardSwitchesArray(QWidget, BoardInput):
    state_changed = Signal(int)
    def __init__(self, count: int):
        super().__init__()
        if count < 1:
            raise ValueError(f"BoardSwitchesArray must have 1+ switch. Received: {count}!")
        self.count = count
        self.checkboxes = [BoardSwitch() for _ in range(count)]
        layout_hook = hbox_factory(*self.checkboxes, no_margins=True)
        self.setLayout(layout_hook)

        for checkbox in self.checkboxes:
            checkbox.toggled.connect(lambda: self.state_changed.emit(self.__get_input_state()))

    def __get_input_state(self) -> int:
        return bool_list_to_int([checkbox.isChecked() for checkbox in self.checkboxes])
    
    @override
    def reset_device(self):
        for switch in self.checkboxes:
            switch.setChecked(False)


class PlusButtons(QWidget, BoardInput):
    state_changed = Signal(dict) # contains dict of button keys -> bool, in
                                 # practice always holding only one item
    def __init__(self, shift_pressed: threading.Event, button_keys: list[str]):
        super().__init__()
        layout_hook = QGridLayout()
        self.setLayout(layout_hook)

        self.BTNU = StickyButton(shift_pressed)
        self.BTND = StickyButton(shift_pressed)
        self.BTNL = StickyButton(shift_pressed)
        self.BTNR = StickyButton(shift_pressed)
        self.BTNC = StickyButton(shift_pressed)
        
        self.buttons_list = [self.BTNU, self.BTND, self.BTNL, self.BTNR, self.BTNC]

        try:
            for button, name in zip(self.buttons_list, button_keys, strict=True):
                button.state_changed.connect(lambda x, n=name: self.state_changed.emit({n: x}))
        except ValueError as e:
            raise ValueError("PlusButtons(): button_keys must be 5 long!") from e

        layout_hook.addWidget(self.BTNU, 0, 1)
        layout_hook.addWidget(self.BTND, 2, 1)
        layout_hook.addWidget(self.BTNL, 1, 0)
        layout_hook.addWidget(self.BTNR, 1, 2)
        layout_hook.addWidget(self.BTNC, 1, 1)
        layout_hook.setSpacing(5)
        layout_hook.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
    
    @override
    def reset_device(self):
        for button in self.buttons_list:
            button.reset_device()

class SegmentType(Enum):
    TOP = auto()
    MIDDLE = auto()
    BOTTOM = auto()
    TOP_LEFT = auto()
    BOTTOM_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_RIGHT = auto()
    DP = auto()

class BoardLight(PushButton):
    '''Use a QPushButton to emulate a light with a fade effect.'''
    def __init__(self, *,
                size: QSize | None = c.Sizes.light,
                on_color: QColor | str = c.Colors.Light.on,
                off_color: QColor | str = c.Colors.Light.off,
                off_time: int = c.light_off_time,
                fade_delay_time: int = c.light_fade_delay_time,
                fade_on: bool = True,
                segment_type: SegmentType | None = None):
        super().__init__()

        self.on_color = QColor(on_color)
        self.off_color = QColor(off_color)
        self.light_on = False
        self.setDisabled(True)
        self.set_color(self.off_color)
        
        if size is not None:
            self.setFixedSize(size)

        self._bg_color = self.on_color

        # TODO: maybe dynamically modify animations so start value matches
        # current value. But this is really not a big deal!!
        self.off_animation = QSequentialAnimationGroup()
        self.off_animation.insertPause(0, fade_delay_time)
        off_fade = QPropertyAnimation(self, b"bg_color")
        off_fade.setStartValue(self.on_color)
        off_fade.setEndValue(self.off_color)
        off_fade.setDuration(off_time - fade_delay_time)
        self.off_animation.addAnimation(off_fade)

        self.fade_on = fade_on

        if fade_on:
            # no fade delay
            self.on_animation = QPropertyAnimation(self, b"bg_color")
            self.on_animation.setStartValue(self.off_color)
            self.on_animation.setEndValue(self.on_color)
            self.on_animation.setDuration(off_time//2)

        self.segment_type = segment_type

    def set_light(self, light_on: bool):
        if self.light_on != light_on: # Avoid redundant color setting
            self.light_on = light_on
            if self.light_on:
                self.off_animation.stop()
                if self.fade_on:
                    self.on_animation.start()
                else:
                    self.set_color(self.on_color)
            else:
                if self.fade_on:
                    self.on_animation.stop()
                self.off_animation.start()

    @Property(QColor)
    def bg_color(self): # pyright: ignore[reportRedeclaration]
        return self._bg_color
    
    @bg_color.setter
    def bg_color(self, val: QColor):
        self._bg_color = val
        
        palette = self.palette() # Copy original palette to modify
        palette.setColor(QPalette.ColorRole.Button, val) # Modify palette copy
        self.setPalette(palette) # Apply modified palette

class BoardLightsArray(QWidget):
    def __init__(self, count: int):
        super().__init__()
        self.count = count
        self.lights = [BoardLight() for _ in range(count)]
        layout_hook = hbox_factory(*self.lights, no_margins=True)
        self.setLayout(layout_hook)
    
    def set_output_state(self, new_state: int):
        for light, state in zip(self.lights, int_to_bool_list(new_state, self.count, invert=False)):
            light.set_light(state)


class SevenSegmentLight(QWidget):
    def __init__(self):
        super().__init__()
        layout_hook = QGridLayout()

        self.CA = BoardLight(size=c.Sizes.horz_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.TOP)
        self.CB = BoardLight(size=c.Sizes.vert_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.TOP_RIGHT)
        self.CC = BoardLight(size=c.Sizes.vert_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.BOTTOM_RIGHT)
        self.CD = BoardLight(size=c.Sizes.horz_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.BOTTOM)
        self.CE = BoardLight(size=c.Sizes.vert_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.BOTTOM_LEFT)
        self.CF = BoardLight(size=c.Sizes.vert_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.TOP_LEFT)
        self.CG = BoardLight(size=c.Sizes.horz_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.MIDDLE)

        self.DP = BoardLight(size=c.Sizes.dp, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.DP)

        layout_hook.addWidget(self.CA, 0, 1) # horizontal bits
        layout_hook.addWidget(self.CG, 2, 1)
        layout_hook.addWidget(self.CD, 4, 1)
        layout_hook.addWidget(self.CF, 1, 0) # left edge
        layout_hook.addWidget(self.CE, 3, 0)
        layout_hook.addWidget(self.CB, 1, 2) # right edge
        layout_hook.addWidget(self.CC, 3, 2)
        # spacing of outer digits layout is set equal to this so DP has that much on either side
        layout_hook.addItem(QSpacerItem(c.Sizes.dp_margin, 0, QSizePolicy.Policy.Fixed), 4, 3)
        layout_hook.addWidget(self.DP, 4, 4) # dot

        layout_hook.setSpacing(0)

        self.lights = [self.CA, self.CB, self.CC, self.CD, self.CE, self.CF, self.CG]

        layout_hook.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout_hook)

    def set_lights(self, lights: int, dp: int, enable: bool):
        if enable:
            for seg, state in zip(self.lights, reversed(int_to_bool_list(lights, 7, invert=True))):
                seg.set_light(state)
            self.DP.set_light(not bool(dp))
        else:
            for light in self.lights:
                light.set_light(False)
            self.DP.set_light(False)

class SevenSegmentGroup(QWidget):
    def __init__(self, count: int):
        super().__init__()
        self.digits = [SevenSegmentLight() for _ in range(count)]
        self.count = count

        self.layout_hook = hbox_factory(*self.digits, no_margins=True)
        self.setLayout(self.layout_hook)

        self.layout_hook.setSpacing(c.Sizes.dp_margin)

        self.setContentsMargins(10, 10, 10, 10)

        # make background gray to make it less harsh on dark mode
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, c.Colors.Segment.background)
        self.setPalette(pal)
        self.setAutoFillBackground(True)

    @Slot(int, int)
    def set(self, cathode: int, dp: int, anode: int):
        for digit, enable in zip(self.digits, int_to_bool_list(anode, self.count, invert=True)):
            digit.set_lights(cathode, dp, enable)

class DotMatrixBlock(QWidget):
    def __init__(self, rows: int, cols: int, spacing: int = 1):
        super().__init__()
        if rows < 1 or cols < 1:
                raise ValueError(f"DotMatrixBlock must be 1+ column and 1+ row. Received: {rows}x{cols}!")
        self.rows, self.cols = rows, cols
        self.lights = [BoardLight(on_color=c.Colors.DotMatrix.on, off_color=c.Colors.DotMatrix.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False) for _ in range(0, rows * cols)]

        layout_hook = QGridLayout()
        layout_hook.setSpacing(spacing)
        self.setLayout(layout_hook)

        count = 0

        row, col = 0, 0 # to type-check to bound after loop

        for row in range(0, rows):
            for col in range(0, cols):
                layout_hook.addWidget(self.lights[count], row, col)
                count += 1

        layout_hook.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding), row+1, col)
        layout_hook.setContentsMargins(0, 0, 0, 0)
    
    def set_lights(self, lights: int, enable: bool):
        if not enable:
            for light in self.lights:
                light.set_light(False)
        else:
            for light, state in zip(self.lights, int_to_bool_list(lights, self.rows * self.cols, invert=False)):
                light.set_light(state)

class DotMatrixGroup(QWidget):
    def __init__(self, count: int, width: int = 3, height: int = 5, inter_spacing: int = 4, intra_spacing: int = 1):
        if count < 1:
            raise ValueError(f"DotMatrixGroup count must be >1. Received: {count}!")
        self.count = count
        super().__init__()
        self.digits = [DotMatrixBlock(height, width, intra_spacing) for _ in range(count)]

        self.layout_hook = hbox_factory(*self.digits, no_margins=True)

        self.layout_hook.setSpacing(inter_spacing)
        self.layout_hook.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, c.Colors.DotMatrix.background)
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        
        self.setLayout(self.layout_hook)

        self.setContentsMargins(10, 10, 10, 10)

    @Slot(int, int)
    def set(self, pattern: int, select: int):
        for digit, enable in zip(self.digits, int_to_bool_list(select, self.count, invert=False)):
            digit.set_lights(pattern, enable)



class AppStyle(QProxyStyle):
    '''Used on virtual boards to change the appearance of some widgets:
    * make SwitchCheckbox into a switch
    * make LightDisplay unshaded and properly shaped: a plain rectangle for
    lights, a rounded rectangle for long segments, and a circle for dots 
    * make StickyButton's two states more distinguishible, especially in dark
    mode (particularly felt very hard to read on Windows on an LCD).'''
    def __init__(self) -> None:
        super().__init__("fusion")

    @override
    def pixelMetric(self, metric, option=None, widget=None): # pyright: ignore[reportMissingParameterType]
        match metric: # modify size of checkboxes
            case QStyle.PixelMetric.PM_IndicatorWidth if isinstance(widget, BoardSwitch):
                return c.Sizes.switch.width()
            case QStyle.PixelMetric.PM_IndicatorHeight if isinstance(widget, BoardSwitch):
                return c.Sizes.switch.height()
            case _:
                return super().pixelMetric(metric, option, widget)

    @override
    def drawPrimitive(self, element: QStyle.PrimitiveElement, option: QStyleOption, painter: QPainter, widget: QWidget | None = None):
        match element:
            case QStyle.PrimitiveElement.PE_FrameFocusRect if isinstance(widget, BoardSwitch):
                pass # don't dim checkboxes
            case QStyle.PrimitiveElement.PE_IndicatorCheckBox if isinstance(widget, BoardSwitch):
                # to vary for dark mode use this to check:
                if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light:
                    back_brush = QBrush(c.Colors.Switch.Light.bg_fill)
                    pen = QPen(c.Colors.Switch.Light.pen)
                    on_brush = QBrush(c.Colors.Switch.Light.on_fill)
                    off_brush = QBrush(c.Colors.Switch.Light.off_fill)
                    focus = c.Colors.Button.Light.focus
                else:
                    back_brush = QBrush(c.Colors.Switch.Dark.bg_fill)
                    pen = QPen(c.Colors.Switch.Dark.pen)
                    on_brush = QBrush(c.Colors.Switch.Dark.on_fill)
                    off_brush = QBrush(c.Colors.Switch.Dark.off_fill)
                    focus = c.Colors.Button.Dark.focus

                pen.setWidthF(.5)
                painter.setPen(pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                bg_rect = QRect(1, 1, c.Sizes.switch.width() - 2, c.Sizes.switch.height() - 2)

                # move top box up or down and color depending on state
                if option.state & QStyle.StateFlag.State_On: # pyright: ignore[reportAttributeAccessIssue] # state seems to be missing from type hints
                    indicator_rect = QRect(3, 3, c.Sizes.switch.width() - 6, c.Sizes.switch.width() - 6)
                    front_brush = on_brush
                else:
                    indicator_rect = QRect(3, 3 + c.Sizes.switch.height() - c.Sizes.switch.width(), c.Sizes.switch.width() - 6, c.Sizes.switch.width() - 6)
                    front_brush = off_brush

                if option.state & QStyle.StateFlag.State_HasFocus: # pyright: ignore[reportAttributeAccessIssue]
                    painter.setPen(QPen(focus))

                painter.setBrush(back_brush)
                painter.drawRoundedRect(bg_rect, 1, 1)
                painter.setPen(pen)
                painter.setBrush(front_brush)
                painter.drawRoundedRect(indicator_rect, 2, 2)
            case _:
                super().drawPrimitive(element, option, painter, widget)
    
    @override
    def drawControl(self, element: QStyle.ControlElement, option: QStyleOption, painter: QPainter, /, widget: QWidget | None = ...) -> None: # pyright: ignore[reportArgumentType]
        match element:
            case QStyle.ControlElement.CE_PushButton if isinstance(widget, StickyButton):
                pen = QPen()
                pen.setWidthF(.75)

                # Light mode: black outline; bright when off; somewhat darker pale blue when on
                if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light:
                    pen.setColor(c.Colors.Button.Light.pen)
                    on_brush = QBrush(c.Colors.Button.Light.on_fill)
                    off_brush = QBrush(c.Colors.Button.Light.off_fill)
                # Dark mode: white outline; dark when off; brighter pale blue when on
                else:
                    pen.setColor(c.Colors.Button.Dark.pen)
                    on_brush = QBrush(c.Colors.Button.Dark.on_fill)
                    off_brush = QBrush(c.Colors.Button.Dark.off_fill)

                # unlike natural Qt buttons, our buttons are down on click.
                #   so draw using union of that and whether they are checked
                is_pressed_in = widget.isDown() or (option.state & QStyle.StateFlag.State_On) # pyright: ignore[reportAttributeAccessIssue]

                if is_pressed_in:
                    brush_to_use = on_brush
                else:
                    brush_to_use = off_brush

                # must draw focus indicator ourself — just make outline blue
                if option.state & QStyle.StateFlag.State_HasFocus: # pyright: ignore[reportAttributeAccessIssue]
                    if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light:
                        pen.setColor(c.Colors.Button.Light.focus)
                    else: # brighter color for dark mode
                        pen.setColor(c.Colors.Button.Dark.focus)
                        if is_pressed_in: # very hard to see focus around blue buttons so make pen wider
                            pen.setWidthF(1.1)

                # bounding box is 14 x 14 but use 1 less on each side to do rounded square
                bg_rect = QRect(1, 1, 12, 12)

                painter.setPen(pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                painter.setBrush(brush_to_use)
                painter.drawRoundedRect(bg_rect, 3, 3)
            case QStyle.ControlElement.CE_PushButton if isinstance(widget, BoardLight):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(widget.palette().color(QPalette.ColorRole.Button))

                rect = QRect(QPoint(1, 1), widget.size() - QSize(2, 2))

                pen = QPen("#333")
                pen.setWidthF(.5)
                painter.setPen(pen)

                # TODO: special drawing for each segment to make things look better
                # for now just makes them not have shading and makes DP a circle
                match widget.segment_type:
                    case SegmentType.DP:
                        x = QPoint(widget.size().width() // 2, widget.size().width() // 2)
                        painter.drawEllipse(x, widget.size().width() // 2 - 1, widget.size().width() // 2 - 1)
                    case None:
                        painter.drawRect(rect)
                    case _:
                        painter.drawRoundedRect(rect, 2, 2)
            case _:
                super().drawControl(element, option, painter, widget)