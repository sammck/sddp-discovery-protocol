#!/usr/bin/env python3

from __future__ import annotations

from sddp_discovery_protocol.internal_types import *

import asyncio
from asyncio import Future
import socket
import struct

from sddp_discovery_protocol.constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

class SddpListenerSession(asyncio.DatagramProtocol):
    final_result: Future[None]
    listener: SddpListener
    transport: Optional[asyncio.DatagramTransport] = None

    def __init__(self, listener: SddpListener, final_result: Future[None]):
        self.listener = listener
        self.final_result = final_result

    def connection_made(self, transport: asyncio.DatagramTransport):
        """Called when a connection is made."""
        print("Connection made")
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """Called when some datagram is received."""

        message = data.decode()
        print(f"[{addr}] {message}")
        # self.transport.sendto(data, addr)

    def error_received(self, exc: Exception):
        """Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        print(f"Error received:  {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost or closed."""
        print(f"Connection lost, exce={exc}")
        self.transport = None
        if exc is None:
          self.final_result.set_result(None)
        else:
          self.final_result.set_exception(exc)

class SddpListener():
    def __init__(self):
        pass

    async def start(self):
        addrinfo = socket.getaddrinfo(SDDP_MULTICAST_ADDRESS, SDDP_PORT)[0]
        sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
        sock.bind(('', SDDP_PORT))
        if addrinfo[0] == socket.AF_INET:
            mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        else:
            assert addrinfo[0] == socket.AF_INET6
            mreq = group_bin + struct.pack('@I', 0)
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

        final_result: Future[None] = Future()

        transport, session = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: SddpListenerSession(self, final_result),
            sock=sock
          )

        await final_result

async def amain() -> None:
    listener = SddpListener()
    await listener.start()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(amain())
