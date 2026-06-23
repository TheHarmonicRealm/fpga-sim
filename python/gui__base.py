import ast
import socket
import textwrap
import threading
import time

from colorama import Fore, Style
from gui__widgets import EmptyWindow
from PySide6.QtCore import QDeadlineTimer, QThread, QTimer, Signal
from shared__util import big_receive


def deserialize_dict(d: str) -> dict:
    return ast.literal_eval(d)

class BaseGUIWindow(EmptyWindow):
    # triggered whenever a model input changes, causing an update to `latest`, the dict sent upwards every non-paused frame
    input_changed = Signal(dict) # really InputDict — but undefined here and not really significant
    # triggered whenever the model output beams back down. COULD: change to only emit when the output is modified but it seems low-overhead
    output_changed = Signal(dict) # really OutputDict — but undefined here and not really significant
    # triggered at the start of each "frame", to send latest up
    input_time = Signal()
    # triggered when the server gives us a response to our sending up of latest
    pinged = Signal()
    # unused -- removed quit button (but still works if i want to bring back)
    close_signal = Signal()
    def __init__(self, title: str, sock: socket.socket, listener_done: threading.Event, have_quit: threading.Event):
        super().__init__(title)
        self.sock = sock
        # important: put thread under self or gc destroys it immediately
        self.t = ListenThread(self, listener_done, have_quit)
        # directly doing this in parent init, which runs before child of course,
        #   does not work because the signals aren't attached to slots by the
        #   time the loop starts and emits them; singleshot delay fixes this
        QTimer.singleShot(0, self.t.start)



class ListenThread(QThread):
    def __init__(self, window: BaseGUIWindow, listener_done: threading.Event, have_quit: threading.Event):
        super().__init__()
        self.window = window

        self.listener_done = listener_done
        self.have_quit = have_quit

    def run(self):
        window = self.window
        sock = window.sock

        # Timer with support for nanosecond precision
        our_timer = QDeadlineTimer()

        while True:
            our_timer.setPreciseRemainingTime(0, nsecs=round(1_000_000_000/60))
            window.input_time.emit()
            # response is either exit or a (maybe empty) list of lines printed by the Verilog program
            response = big_receive(sock).decode()
            window.pinged.emit() # update FPS after receiving

            if response == "exit":
                print("Got exit")
                self.listener_done.set()
                break
            else:
                verilog_prints = ast.literal_eval(response)
                if len(verilog_prints) > 0:
                    message = "\n".join([textwrap.indent(s, " " * 4) for s in verilog_prints])
                    print(f"{Fore.BLUE}{Style.BRIGHT}{message}{Style.RESET_ALL}")

                # get the output dict expected after the Verilog list
                output_state = deserialize_dict(big_receive(sock).decode()) # really OutputDict
                if not self.have_quit.is_set(): # make sure to not do Qt stuff if app has quit. (Not sure if necessary)
                    window.output_changed.emit(output_state)

            while not our_timer.hasExpired():
                time.sleep(.0001)