from collections.abc import Callable
from enum import Enum, auto
from threading import Event
from typing import Literal, overload, override

import gui__constants as c
from PySide6.QtCore import (
    Property,
    QObject,
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
    QAction,
    QBrush,
    QColor,
    QGuiApplication,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QMainWindow,
    QProxyStyle,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)
from shared__util import bool_list_to_int, int_to_bool_list


def set_color(button: QPushButton | QRadioButton, color: str | QColor):
    '''Sets the most relevant color of the given widget using palettes.
    May expand to more widgets at some point eventually.'''

    palette = button.palette() # Copy original palette to modify

    if isinstance(color, str): # Construct QColor if given string
        color = QColor(color)

    match button:
        case QPushButton():
            role = QPalette.ColorRole.Button
        case QRadioButton():
            role = QPalette.ColorRole.Base
        case _:
            raise TypeError(f"set_color() given bad-type widget {button}")

    palette.setColor(role, color) # Modify palette copy
    button.setPalette(palette) # Apply modified palette

def mix_colors(color1: QColor, color2: QColor):
    # Finds the "middle color" of two colors through simple averaging.
    # Not perception adjusted or anything.
    return QColor(round(color1.red()/2 + color2.red()/2), round(color1.green()/2 + color2.green()/2), round(color1.blue()/2 + color2.blue()/2))

class EmptyWindow(QMainWindow):
    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)

        self.main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        self.shift_pressed = Event()

        self.old_pos = self.pos()

    # Make window draggable from anywhere
    # (Added to allow moving while frameless)
    @override
    def mousePressEvent(self, event: QMouseEvent):
        # if not filtered, right-click is wonky on Ubuntu/Wayland
        if event.button() == Qt.MouseButton.LeftButton:
            self.windowHandle().startSystemMove()

    @override
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Shift:
            self.shift_pressed.set()
    @override
    def keyReleaseEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Shift:
            self.shift_pressed.clear()

# Narrow type so type checker is happy with vbox/hbox calls
@overload
def __box_factory(*stuff: QLayout | QWidget, vertical: Literal[True], no_margins: bool = True) -> QVBoxLayout: ...
@overload
def __box_factory(*stuff: QLayout | QWidget, vertical: Literal[False], no_margins: bool = True)  -> QHBoxLayout: ...

def __box_factory(*stuff: QLayout | QWidget, vertical: bool, no_margins: bool = True):
    box = QVBoxLayout() if vertical else QHBoxLayout()
    for item in stuff:
        if isinstance(item, QLayout):
            box.addLayout(item)
        elif isinstance(item, QWidget):
            box.addWidget(item)
        else:
            raise TypeError(f"__box_factory() (helper to [vbox|hbox]_factory) passed non-layout/widget {item} of type {type(item)}!")
    if no_margins:
        box.setContentsMargins(0, 0, 0, 0)
    return box

def vbox_factory(*stuff: QLayout | QWidget, no_margins: bool = True) -> QVBoxLayout:
    return __box_factory(*stuff, vertical=True, no_margins=no_margins)

def hbox_factory(*stuff: QLayout | QWidget, no_margins: bool = True) -> QHBoxLayout:
    return __box_factory(*stuff, vertical=False, no_margins=no_margins)

def make_button(text: str, function: Callable, *, tooltip: str=""):
    bt = QPushButton(text)
    bt.pressed.connect(function)
    if tooltip:
        bt.setToolTip(tooltip)
    return bt

def make_checkbox(text: str, function: Callable[[bool], ], *, checked: bool=False, tooltip: str=""):
    cb = QCheckBox(text)
    cb.toggled.connect(function)
    cb.setChecked(checked)
    if tooltip:
        cb.setToolTip(tooltip)
    return cb

def make_action(name: str,  function: Callable, shortcut: QKeySequence | str, parent: QObject):
    ac = QAction(name, parent)
    ac.setShortcut(shortcut)
    ac.setAutoRepeat(False)
    ac.triggered.connect(function)
    return ac

class AppStyle(QProxyStyle):
    '''Applied to checkboxes in `make_switch_checkbox()` to make them look like
    vertical binary switches.'''
    def __init__(self) -> None:
        super().__init__("fusion")

    @override
    def pixelMetric(self, metric, option=None, widget=None):
        match metric: # modify size of checkboxes
            case QStyle.PixelMetric.PM_IndicatorWidth if isinstance(widget, SwitchCheckbox):
                return c.Sizes.switch.width()
            case QStyle.PixelMetric.PM_IndicatorHeight if isinstance(widget, SwitchCheckbox):
                return c.Sizes.switch.height()
            case _:
                return super().pixelMetric(metric, option, widget)

    @override
    def drawPrimitive(self, element: QStyle.PrimitiveElement, option: QStyleOption, painter: QPainter, widget: QWidget | None = None):
        match element:
            case QStyle.PrimitiveElement.PE_FrameFocusRect if isinstance(widget, SwitchCheckbox):
                pass # don't dim checkboxes
            case QStyle.PrimitiveElement.PE_IndicatorCheckBox if isinstance(widget, SwitchCheckbox):
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
            case QStyle.ControlElement.CE_PushButton if isinstance(widget, LightDisplay):
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

def make_app(argv: list[str] = []):
    app = QApplication(argv)
    app.setStyle(AppStyle())
    return app

# The below classes are used inside BoardComponents.

class SwitchCheckbox(QCheckBox):
    '''Checkbox that has the appearance of a vertical on/off switch, if
    style is applied'''
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(c.Sizes.switch)

class StickyButton(QPushButton):
    '''Button with somewhat custom style that stays down if shift is held when
    released. Style is overridden in AppStyle, mainly because the default's
    state is quite hard to read in dark mode on both Mac and Windows 11.'''
    sticky_press = Signal()
    sticky_release = Signal()
    def __init__(self, shift_pressed: Event):
        super().__init__()
        self.setFixedSize(c.Sizes.light)
        self.setCheckable(True)
        self.released.connect(self.maybe_uncheck)
        self.shift_pressed = shift_pressed

        self.pressed.connect(self.handle_press_emit)
        self.toggled.connect(self.handle_release_emit)

    def handle_press_emit(self):
        if not self.isChecked():
            self.sticky_press.emit()

    def handle_release_emit(self, now_checked: bool):
        if not now_checked:
            self.sticky_release.emit()
    
    def maybe_uncheck(self):
        if self.isChecked() and not self.shift_pressed.is_set():
            self.setChecked(False)

class SegmentType(Enum):
    TOP = auto()
    BOTTOM = auto()
    TOP_LEFT = auto()
    MIDDLE = auto()
    BOTTOM_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_RIGHT = auto()
    DP = auto()

class LightDisplay(QPushButton):
    '''Misused QPushButton used to emulate a light with a fade effect.'''
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
        set_color(self, self.off_color)
        
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
                    set_color(self, self.on_color)
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

#   AAAA
#  F    B
#   GGGG
#  E    C
#   DDDD

# Nothing implementation-specific until here

    
def make_light(*, horiz: bool, seg_type: SegmentType):
    return LightDisplay(size=c.Sizes.horz_light if horiz else c.Sizes.vert_light, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=seg_type)

def make_dp():
    return LightDisplay(size=c.Sizes.dp, on_color=c.Colors.Segment.on, off_color=c.Colors.Segment.off, fade_delay_time=c.segment_fade_delay_time, off_time=c.segment_off_time, fade_on=False, segment_type=SegmentType.DP)

class SevenSegmentLight:
    def __init__(self):
        super().__init__()
        self.layout = QGridLayout()

        self.CA = make_light(horiz=True, seg_type=SegmentType.TOP)
        self.CB = make_light(horiz=False, seg_type=SegmentType.TOP_RIGHT)
        self.CC = make_light(horiz=False, seg_type=SegmentType.BOTTOM_RIGHT)
        self.CD = make_light(horiz=True, seg_type=SegmentType.BOTTOM)
        self.CE = make_light(horiz=False, seg_type=SegmentType.BOTTOM_LEFT)
        self.CF = make_light(horiz=False, seg_type=SegmentType.TOP_LEFT)
        self.CG = make_light(horiz=True, seg_type=SegmentType.MIDDLE)
        # At tiny size, rounded square is close enough to a dot
        self.DP = make_dp()

        self.layout.addWidget(self.CA, 0, 1) # horizontal bits
        self.layout.addWidget(self.CG, 2, 1)
        self.layout.addWidget(self.CD, 4, 1)
        self.layout.addWidget(self.CF, 1, 0) # left edge
        self.layout.addWidget(self.CE, 3, 0)
        self.layout.addWidget(self.CB, 1, 2) # right edge
        self.layout.addWidget(self.CC, 3, 2)
        # spacing of outer digits layout is set equal to this so DP has that much on either side
        self.layout.addItem(QSpacerItem(c.Sizes.dp_margin, 0, QSizePolicy.Policy.Fixed), 4, 3)
        self.layout.addWidget(self.DP, 4, 4) # dot

        self.layout.setSpacing(0)

        self.lights = [self.CA, self.CB, self.CC, self.CD, self.CE, self.CF, self.CG]

    def set_lights(self, lights: int, dp: int, enable: bool):
        if enable:
            for seg, state in zip(self.lights, reversed(int_to_bool_list(lights, 7, invert=True))):
                seg.set_light(state)
            self.DP.set_light(not bool(dp))
        else:
            for light in self.lights:
                light.set_light(False)
            self.DP.set_light(False)

class BoardComponents:
    class FourDigits(QWidget):
        def __init__(self):
            super().__init__()
            self.digits = [SevenSegmentLight() for _ in range(4)]

            self.layout_hook = hbox_factory(*[digit.layout for digit in self.digits], no_margins=True)
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
            for digit, enable in zip(self.digits, int_to_bool_list(anode, 4, invert=True)):
                digit.set_lights(cathode, dp, enable)


    class Switches(QWidget):
        state_changed = Signal(int)
        def __init__(self):
            super().__init__()
            self.checkboxes = [SwitchCheckbox() for _ in range(0, 16)]
            layout_hook = hbox_factory(*self.checkboxes, no_margins=True)

            layout_hook.addItem(QSpacerItem(10, 0, QSizePolicy.Policy.Expanding))
            self.setLayout(layout_hook)

            for checkbox in self.checkboxes:
                checkbox.toggled.connect(lambda: self.state_changed.emit(self.__get_input_state()))

        @Slot(int)
        def set_input_state(self, new_state: int):
            # Block the 16 auto-emits and do a manual emit with new state
            self.blockSignals(True)
            for checkbox, state in zip(self.checkboxes, int_to_bool_list(new_state, 16, invert=False)):
                checkbox.setChecked(state)
            self.state_changed.emit(self.__get_input_state())
            self.blockSignals(False)

        def __get_input_state(self) -> int:
            return bool_list_to_int([checkbox.isChecked() for checkbox in self.checkboxes])

    class Lights(QWidget):
        def __init__(self):
            super().__init__()
            self.lights = [LightDisplay() for _ in range(0, 16)]
            layout_hook = hbox_factory(*self.lights, no_margins=True)
            layout_hook.addItem(QSpacerItem(10, 0, QSizePolicy.Policy.Expanding))
            self.setLayout(layout_hook)
        
        def set_output_state(self, new_state: int):
            for light, state in zip(self.lights, int_to_bool_list(new_state, 16, invert=False)):
                light.set_light(state)

    class Buttons(QWidget):
        state_changed = Signal(int)
        def __init__(self, shift_pressed: Event) -> None:
            super().__init__()
            layout_hook = QGridLayout()
            self.setLayout(layout_hook)

            self.BTNU = StickyButton(shift_pressed)
            self.BTND = StickyButton(shift_pressed)
            self.BTNL = StickyButton(shift_pressed)
            self.BTNR = StickyButton(shift_pressed)
            self.BTNC = StickyButton(shift_pressed)

            self.buttons_list = [self.BTNU, self.BTND, self.BTNL, self.BTNR, self.BTNC]

            for button in self.buttons_list:
                button.sticky_press.connect(lambda b=button: self.state_changed.emit(self.__get_input_state(b)))
                button.sticky_release.connect(lambda: self.state_changed.emit(self.__get_input_state()))

            layout_hook.addWidget(self.BTNU, 0, 1)
            layout_hook.addWidget(self.BTND, 2, 1)
            layout_hook.addWidget(self.BTNL, 1, 0)
            layout_hook.addWidget(self.BTNR, 1, 2)
            layout_hook.addWidget(self.BTNC, 1, 1)
            layout_hook.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding), 0, 3)

        def __get_input_state(self, new_button: StickyButton | None = None) :
            # new_button is forced to true if provided; it is currently pressed but not checked
            output_list = [b.isChecked() if b is not new_button else True for b in self.buttons_list]
            return bool_list_to_int(output_list)