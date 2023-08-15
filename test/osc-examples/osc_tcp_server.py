"""OSC Servers that receive UDP packets and invoke handlers accordingly.
"""

import asyncio
import os
import socketserver

from pythonosc import osc_bundle
from pythonosc import osc_message
from pythonosc.dispatcher import Dispatcher

from asyncio import BaseEventLoop

from socket import socket as _socket
from typing import Any, Tuple, Union, cast, Coroutine

_RequestType = Union[_socket, Tuple[bytes, _socket]]
_AddressType = Union[Tuple[str, int], str]


class _TCPHandler(socketserver.BaseRequestHandler):
    """Handles correct UDP messages for all types of server."""

    def handle(self) -> None:
        """Calls the handlers via dispatcher

        This method is called after a basic sanity check was done on the datagram,
        whether this datagram looks like an osc message or bundle.
        If not the server won't call it and so no new
        threads/processes will be spawned.
        """
        server = cast(OSCTCPServer, self.server)
        server.dispatcher.call_handlers_for_packet(self.request.recv(1024), self.client_address)


def _is_valid_request(request: _RequestType) -> bool:
    """Returns true if the request's data looks like an osc bundle or message.

    Returns:
        True if request is OSC bundle or OSC message
    """
    data = request.recv(4096)
    return (
            osc_bundle.OscBundle.dgram_is_bundle(data)
            or osc_message.OscMessage.dgram_is_message(data))


class OSCTCPServer(socketserver.TCPServer):
    """Superclass for different flavors of OSC UDP servers"""

    def __init__(self, server_address: Tuple[str, int], dispatcher: Dispatcher, bind_and_activate: bool = True) -> None:
        """Initialize

        Args:
            server_address: IP and port of server
            dispatcher: Dispatcher this server will use
            (optional) bind_and_activate: default=True defines if the server has to start on call of constructor  
        """
        super().__init__(server_address, _TCPHandler, bind_and_activate)
        self._dispatcher = dispatcher

    def verify_request(self, request: _RequestType, client_address: _AddressType) -> bool:
        """Returns true if the data looks like a valid OSC UDP datagram

        Args:
            request: Incoming data
            client_address: IP and port of client this message came from

        Returns:
            True if request is OSC bundle or OSC message
        """
        valid = _is_valid_request(request)
        return valid

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher


class ThreadingOSCTCPServer(socketserver.ThreadingMixIn, OSCTCPServer):
    """Threading version of the OSC UDP server.

    Each message will be handled in its own new thread.
    Use this when lightweight operations are done by each message handlers.
    """
