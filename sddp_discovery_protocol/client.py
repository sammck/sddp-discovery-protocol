#!/usr/bin/env python3

"""
An SDDP server that can:

   1. Listen for datagrams received on the SDDP multicast address (Typically 239.255.255.250:1902)
   2. Collect and maintain a dictionary of actively advertising SDDP devices, with associated metadata
   3. Optionally, send out a periodic multicast message advertising a local device
   4. Optionally, respond to SDDP discovery requests with a configured response
"""

from __future__ import annotations


import asyncio
from asyncio import Future
import socket
import struct

from sddp_discovery_protocol.internal_types import *
from .pkg_logging import logger
from .constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

from .sddp_datagram import SddpDatagram

MAX_QUEUE_SIZE = 1000

class _SddpMulticastClientProtocol(asyncio.DatagramProtocol):
    server: SddpMulticastServer
    transport: Optional[asyncio.DatagramTransport] = None

    def __init__(self, server: SddpMulticastServer):
        self.server = server

    def connection_made(self, transport: asyncio.DatagramTransport):
        """Called when a connection is made."""
        assert self.transport is None
        try:
            self.transport = transport
            self.server.connection_made(transport)
        except BaseException as e:
            self.server.set_final_exception(e)
            raise

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """Called when some datagram is received."""
        try:
            self.server.datagram_received(data, addr)
        except BaseException as e:
            self.server.set_final_exception(e)
            raise

    def error_received(self, exc: Exception):
        """Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        try:
            self.server.error_received(exc)
        except BaseException as e:
            self.server.set_final_exception(e)
            raise

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost or closed."""
        try:
            self.server.connection_lost(exc)
        except BaseException as e:
            self.server.set_final_exception(e)
            raise
        self.transport = None



class SddpDatagramSubscriber:
    server: SddpMulticastServer
    queue: asyncio.Queue[Optional[Tuple[HostAndPort, SddpDatagram]]]
    final_result: Future[None]
    eos: bool = False
    eos_exc: Optional[Exception] = None


    def __init__(self, server: SddpMulticastServer, max_queue_size: int = MAX_QUEUE_SIZE):
        self.server = server
        self.queue = asyncio.Queue(max_queue_size)
        self.final_result = Future()

    async def __aenter__(self) -> SddpDatagramSubscriber:
        await self.server.add_subscriber(self)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self.server.remove_subscriber(self)
        self.set_final_result()
        try:
            # ensure that final_result has been awaited
            await self.final_result
        except BaseException as e:
            pass
        return False

    async def iter_datagrams(self) -> AsyncIterator[Tuple[HostAndPort, SddpDatagram]]:
        while True:
            result = await self.receive()
            if result is None:
                break
            yield result

    def set_final_result(self) -> None:
        if not self.final_result.done():
            self.final_result.set_result(None)
            if not self.queue is None:
                # wake up any waiting tasks
                try:
                    self.queue.put_nowait(None)
                except asyncio.QueueFull:
                    # queue is full so waiters will wake up soon
                    pass
            self.eos = True
            self.eos_exc = None

    def set_final_exception(self, e: BaseException) -> None:
        if not self.final_result.done():
            self.final_result.set_exception(e)
            if not self.queue is None:
                # wake up any waiting tasks
                try:
                    self.queue.put(None)
                except asyncio.QueueFull:
                    # queue is full so waiters will wake up soon
                    pass
            self.eos = True
            self.eos_exc = None

    async def receive(self) -> Optional[Tuple[HostAndPort, SddpDatagram]]:
        if self.final_result.done():
            await self.final_result
            return None
        if self.eos and self.queue.empty():
            if self.eos_exc is None:
                self.set_final_result()
            else:
                self.set_final_exception(self.eos_exc)
            await self.final_result
            return None
        try:
          result =  await self.queue.get()
          self.queue.task_done()
          if result is None:
              if not self.final_result.done():
                  assert self.eos
                  if self.eos_exc is None:
                      self.set_final_result()
                  else:
                      self.set_final_exception(self.eos_exc)
              await self.final_result
              return None
        except BaseException as e:
            self.set_final_exception(e)
            raise
        return result

    def on_datagram(self, addr: HostAndPort, datagram: SddpDatagram) -> None:
        if not self.eos and not self.final_result.done():
            try:
                self.queue.put_nowait((addr, datagram))
            except asyncio.QueueFull:
                logger.warning(f"Queue full, dropping datagram from {addr}: {datagram}")

    def on_end_of_stream(self, exc: Optional[Exception]=None) -> None:
        if not self.eos and not self.final_result.done():
            self.eos = True
            self.eos_exc = exc
            try:
                # wake up any waiting tasks
                self.queue.put_nowait(None)
            except asyncio.QueueFull:
                # queue is full so waiters will wake up soon
                pass

class SddpMulticastServer:
    """
    An SDDP server that can:

      1. Listen for datagrams received on the SDDP multicast address (Typically 239.255.255.250:1902)
      2. Collect and maintain a dictionary of actively advertising SDDP devices, with associated metadata
      3. Optionally, send out a periodic multicast message advertising a local device
      4. Optionally, respond to SDDP discovery requests with a configured response
    """

    receive_task: Optional[asyncio.Task[None]] = None
    """A background task that receives datagrams and processes them."""

    transport: Optional[asyncio.DatagramTransport] = None
    """The asyncio transport used to receive and send datagrams."""

    protocol: Optional[_SddpMulticastServerProtocol] = None
    """the adapter between the asyncio transport and this class."""

    final_result: Future[None]
    """A future that is set when the server is stopped."""

    datagram_subscribers: Set[SddpDatagramSubscriber] = set()
    """A set of subscribers that wish to receive SDDP Datagrams."""

    device_collector_task: Optional[asyncio.Task[None]] = None

    def __init__(self):
        self.final_result = Future()

    async def add_subscriber(self, subscriber: SddpDatagramSubscriber) -> None:
        self.datagram_subscribers.add(subscriber)

    async def remove_subscriber(self, subscriber: SddpDatagramSubscriber) -> None:
        self.datagram_subscribers.remove(subscriber)

    async def start(self) -> None:
        try:
            loop = asyncio.get_running_loop()
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
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _SddpMulticastServerProtocol(self),
                sock=sock
              )
            self.protocol = protocol
            if self.transport is None:
                self.transport = transport
            else:
                assert self.transport == transport

            self.device_collector_task = asyncio.create_task(self._device_collector_task())

        except BaseException as e:
            self.set_final_exception(e)
            raise

    async def stop(self) -> None:
        if self.transport is not None:
            try:
                self.transport.close()
            except BaseException as e:
                logger.error(f"Error closing transport: {e}")
            self.transport = None

    async def wait_for_done(self) -> None:
        await self.final_result
        if self.device_collector_task is not None:
            await self.device_collector_task
            self.device_collector_task = None

    async def stop_and_wait(self) -> None:
        await self.stop()
        await self.wait_for_done()


    def connection_made(self, transport: asyncio.DatagramTransport):
        """Called when a connection is made."""
        logger.debug("Connection made")
        if self.transport is None:
            self.transport = transport
        else:
            assert self.transport == transport

    def datagram_received(self, data: bytes, addr: HostAndPort):
        """Called when some datagram is received."""
        try:
            datagram = SddpDatagram(raw_data=data)
            logger.debug(f"Received datagram from {addr}: {datagram}")
            subscribers = list(self.datagram_subscribers)
            for subscriber in subscribers:
                try:
                    subscriber.on_datagram(addr, datagram)
                except BaseException as e:
                    logger.warning(f"Subscriber raised exception processing datagram {datagram}: {e}")
        except BaseException as e:
            logger.warning(f"Error parsing datagram from {addr}, raw=[{data}]: {e}")
        # self.transport.sendto(data, addr)

    def error_received(self, exc: Exception) -> None:
        """Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        logger.info(f"Error received from transport: {exc}")
        subscribers = list(self.datagram_subscribers)
        for subscriber in subscribers:
            try:
                subscriber.on_end_of_stream(exc)
            except BaseException as e:
                logger.warning(f"Subscriber raised exception processing transport error: {e}")
        self.set_final_exception(exc)


    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost or closed."""
        logger.info(f"Connection to transport lost, exc={exc}")
        self.transport = None
        subscribers = list(self.datagram_subscribers)
        for subscriber in subscribers:
            try:
                subscriber.on_end_of_stream(exc)
            except BaseException as e:
                logger.warning(f"Subscriber raised exception processing transport connection loss: {e}")
        if exc is None:
            self.set_final_result()
        else:
            self.set_final_exception(exc)

    def set_final_exception(self, exc: BaseException) -> None:
        assert not exc is None
        if not self.final_result.done():
            self.final_result.set_exception(exc)
        if not self.transport is None:
            try:
                self.transport.close()
            except BaseException as e:
                logger.error(f"Error closing transport: {e}")
            self.transport = None

    def set_final_result(self) -> None:
        if not self.final_result.done():
            self.final_result.set_result(None)
        if not self.transport is None:
            try:
                self.transport.close()
            except BaseException as e:
                logger.error(f"Error closing transport: {e}")
            self.transport = None


    async def _device_collector_task(self) -> None:
        logger.debug("Device collector task starting")
        try:
            async with SddpDatagramSubscriber(self) as subscriber:
                async for addr, datagram in subscriber.iter_datagrams():
                    logger.debug(f"Collector received datagram from {addr}: {datagram}")
        except BaseException as e:
            logger.warning(f"Device collector task exiting with exception: {e}")
            raise
        logger.debug("Device collector task exiting")

if __name__ == "__main__":
  import logging

  async def amain() -> None:
      server = SddpMulticastServer()
      await server.start()
      try:
          await asyncio.wait_for(asyncio.shield(server.wait_for_done()), timeout=5.0)
      except asyncio.TimeoutError:
          logger.info("Time passed with no errors; shutting down")
          await server.stop_and_wait()


  logging.basicConfig(
      level=logging.getLevelName('DEBUG'),
      format="%(asctime)s %(levelname)s %(filename)s:%(lineno)d] %(message)s",
      datefmt="%F %H:%M:%S")

  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  loop.run_until_complete(amain())
