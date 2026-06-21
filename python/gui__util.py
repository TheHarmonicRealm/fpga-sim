"""Functions not related to widgets but used only in the GUI
so not necessary to copy over to the server"""

import socket


def reconstruct_socket_unix(sock_id: int):
    sock_fd = sock_id
    return socket.fromfd(sock_fd, socket.AF_INET, socket.SOCK_STREAM)


def reconstruct_socket_windows(socket_share_data: bytes):
    return socket.fromshare(socket_share_data)
