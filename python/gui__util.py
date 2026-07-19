"""Functions not related to widgets but used only in the GUI
so not necessary to copy over to the server"""

import socket
import sys


def reconstruct_socket_unix(sock_id: int):
    if sys.platform == 'win32':
        raise OSError("Called Unix socket function on Windows!")
    sock_fd = sock_id
    return socket.fromfd(sock_fd, socket.AF_INET, socket.SOCK_STREAM)


def reconstruct_socket_windows(socket_share_data: bytes):
    if sys.platform != 'win32':
        raise OSError("Called Windows socket function on non-Windows!")
    return socket.fromshare(socket_share_data) # type: ignore
