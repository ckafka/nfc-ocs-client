""" TCP Client for OSC messages"""

import socket
from pythonosc.osc_message_builder import OscMessageBuilder


class OscTcpClient:
    """OSC TCP Client"""

    def __init__(self, ip, port):
        self.osc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.osc_socket.connect((ip, port))

    def send_message(self, address: str, value) -> None:
        """Build :class:`OscMessage` from arguments and send to server

        Args:
            address: OSC address the message shall go to
            value: One or more arguments to be added to the message
        """
        builder = OscMessageBuilder(address=address)
        if value is None:
            values = []
        else:
            values = value
        for val in values:
            builder.add_arg(val)
        msg = builder.build()
        self.osc_socket.send(msg)
