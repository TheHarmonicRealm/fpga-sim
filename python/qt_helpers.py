'''Base Qt things, imported to create specific widgets for boards.'''

import os
import sys
import threading
from typing import Literal, overload, override
from collections.abc import Callable
from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QEnterEvent, QKeyEvent, QKeySequence, QMouseEvent, QPalette
from PySide6.QtWidgets import QCheckBox, QGraphicsOpacityEffect, QHBoxLayout, QLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget


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

class PushButton(QPushButton):
    '''Simple subclass to allow a nice .new constructor and to let set_color be
    part of the class.'''
    def set_color(self, color: str | QColor):
        p = self.palette() # Copy original palette to modify
        p.setColor(QPalette.ColorRole.Button, color) # Modify palette copy
        self.setPalette(p) # Apply modified palette

    @classmethod
    def new(cls, text: str, function: Callable, *, tooltip: str=""):
        b = PushButton(text)
        b.pressed.connect(function)
        if tooltip:
            b.setToolTip(tooltip)
        return b


def make_button(text: str, function: Callable, *, tooltip: str=""):
    return PushButton.new(text, function, tooltip=tooltip)

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



class _ForbidFilter(QObject):
    def __init__(self, /, parent: QObject | None = None, *, objectName: str | None = None) -> None:
        super().__init__(parent, objectName=objectName)
        self.cant_cursor = False

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QEnterEvent) and not self.cant_cursor:
            try:
                watched.setCursor(Qt.CursorShape.ForbiddenCursor) # pyright: ignore[reportAttributeAccessIssue]
                return True
            except AttributeError:
                print(f"_ForbidFilter: Can't set cursor of a {watched.__qualname__}")
                self.cant_cursor = True
                return True
        if isinstance(event, QMouseEvent):
            return True
        else:
            return QObject.eventFilter(self, watched, event)

def pseudo_disable(w: QWidget, tooltip: str, *, checked: bool | None = None):
    '''Makes a widget act disabled, adding a ForbiddenCursor. Sets opacity low,
    prevents keyboard focus and ignores mouse clicks, sets a tooltip, and sets
    check state if desired.'''
    w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    w.setGraphicsEffect(QGraphicsOpacityEffect(w, opacity=.5))
    w._forbid_filter = _ForbidFilter() # pyright: ignore[reportAttributeAccessIssue]
    w.installEventFilter(w._forbid_filter) # pyright: ignore[reportAttributeAccessIssue]
    w.setToolTip(tooltip)
    w.blockSignals(True)
    if checked is not None:
        try:
            w.setChecked(checked) # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError:
            print(f"pseudo_disable(): can't check/uncheck a {w.__qualname__}!")

class EmptyWindow(QMainWindow):
    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)

        self.main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        self.shift_pressed = threading.Event()

        self.is_wayland = "WAYLAND_DISPLAY" in os.environ

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

    
    def set_frameless(self, enable: bool):
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, enable)

        if sys.platform == 'win32':
            if not enable:
                # nudge a tiny bit to fix issue where size is wrong after
                #   made frameful, then wait a tiny bit before going home
                target_pos = self.pos() - QPoint(0, 30) 
                QTimer.singleShot(0, lambda: self.move(self.pos() + QPoint(1, 0)))
                QTimer.singleShot(50, lambda: self.move(target_pos))
            else: # move down by size of top bar
                QTimer.singleShot(0, lambda: self.move(self.pos() + QPoint(0, 30)))
        elif sys.platform == 'darwin':
            if enable:
                self.move(self.pos() + QPoint(0, 28))
            else:
                self.move(self.pos() + QPoint(0, -28))
        self.show()

    def set_on_top(self, enable: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enable)
        self.show()
