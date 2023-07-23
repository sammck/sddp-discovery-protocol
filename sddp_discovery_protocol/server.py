#!/usr/bin/env python3

"""
SddpServer -- An SDDP server that can:

  1. Listen on a multicast UDP address (typically 239.255.255.250:1902)
  2. Receive and decode SddpDatagrams from remote nodes and deliver them to any number of async subscribers
  3. Respond to SDDP discovery requests with a configured response
  4. Optionally, send out a periodic multicast message advertising a configured local device
  5. Collect, maintain, and expire advertisements broadcasted by other devices on the network
"""

from __future__ import annotations


import asyncio
from asyncio import Future
import socket
import sys
import re

from sddp_discovery_protocol.internal_types import *
from .pkg_logging import logger
from .constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

from .sddp_datagram import SddpDatagram
from .sddp_socket import SddpSocket, SddpSocketBinding, SddpDatagramSubscriber
from .util import get_local_ip_addresses

DEFAULT_MAX_AGE = 1800

IP_MULTICAST_ALL = 49
IPV6_MULTICAST_ALL = 41

class SddpServer(SddpSocket):
    """
    An SDDP server that can:

      1. Listen for datagrams received on the SDDP multicast address (Typically 239.255.255.250:1902)
      3. Optionally, send out a periodic multicast message advertising the local device
      4. Optionally, respond to SDDP discovery requests with a configured response
    """

    advertise_datagram: Optional[SddpDatagram] = None
    """The datagram to send as an SDDP advertisement."""

    advertise_interval: float = 0.0
    """The interval (in seconds) at which to send out SDDP advertisements. If 0.0, no advertisements
        will be sent. By default 2/3 of the Max-Age header value will be used."""

    respond_to_queries: bool = True
    """If True, this server will respond to SDDP queries with a configured response. If False, queries
        will be ignored."""

    collector_task: Optional[asyncio.Task[None]] = None
    """The task that collects device advertisements from the network. If None, no device advertisements
        are being collected."""

    responder_task: Optional[asyncio.Task[None]] = None
    """The task that responds to device queries from the network. If None, queries will be ignored."""

    advertiser_task: Optional[asyncio.Task[None]] = None
    """The task that broadcasts periodic local device advertisements to the multicast address.
       If None, no advertisements will be sent."""

    collected_advertisements: Dict[Tuple[HostAndPort, str], SddpDatagram]
    """A dictionary of collected advertisements. The key is a tuple of (host, port, advertised_hostname)."""

    multicast_address: str = SDDP_MULTICAST_ADDRESS
    """The multicast address to listen on and advertise to."""

    multicast_port: int = SDDP_PORT
    """The multicast port to listen on and advertise to."""

    bind_addresses: List[str]

    def __init__(
            self,
            device_headers: Optional[Mapping[str, str | int | float | None]]=None,
            advertise_interval: Optional[float]=None,
            respond_to_queries: bool=True,
            multicast_address: str=SDDP_MULTICAST_ADDRESS,
            multicast_port: int=SDDP_PORT,
            bind_addresses: Optional[Iterable[str]]=None,
          ) -> None:
        super().__init__()
        advertise_datagram = SddpDatagram(statement='NOTIFY ALIVE SDDP/1.0', headers=device_headers)
        self.advertise_datagram = advertise_datagram
        if advertise_datagram.hdr_max_age is None:
            advertise_datagram.hdr_max_age = DEFAULT_MAX_AGE
        if advertise_interval is None:
            advertise_interval = advertise_datagram.hdr_max_age * (2 / 3)
        self.advertise_interval = advertise_interval
        self.respond_to_queries = respond_to_queries
        self.multicast_address = multicast_address
        self.multicast_port = multicast_port
        self.collected_advertisements = {}
        if bind_addresses is None:
            bind_addresses = get_local_ip_addresses()
        self.bind_addresses = list(bind_addresses)

    #@override
    async def add_socket_bindings(self) -> None:
        """Abstract method that creates and binds the sockets that will be used to receive
           and send datagrams (typically one per interface), and adds them with self.add_socket_binding().
           Must be overridden by subclasses."""

        # Create a socket for each bind address
        addrinfo = socket.getaddrinfo(self.multicast_address, self.multicast_port)[0]
        address_family = addrinfo[0]
        assert address_family in (socket.AF_INET, socket.AF_INET6)
        is_ipv6 = address_family == socket.AF_INET6
        group_bin = socket.inet_pton(address_family, addrinfo[4][0])
        for bind_address in self.bind_addresses:
            sock = socket.socket(address_family, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            # On Linux, disabling IP_MULTICAST_ALL ensures that each socket only receives
            # multicast packets sent to the multicast address on the interface that the
            # socket is bound to.  Without doing this, every multicast is received by all sockets
            # bound to 0.0.0.0:<port> even if IP_ADD_MEMBERSHIP for the socket includes a filter for
            # the bind address. If there are multiple bound sockets, This would result in duplicate
            # packets being received by subscribers, with incorrect SddpBoundSocket values.
            if sys.platform in ('linux', 'linux2'):
                sock.setsockopt(socket.IPPROTO_IP, IPV6_MULTICAST_ALL if is_ipv6 else IP_MULTICAST_ALL, 0)
            sock.bind(('', SDDP_PORT))
            bind_bin_addr = socket.inet_pton(address_family, bind_address)
            if is_ipv6:
                assert address_family == socket.AF_INET6
                mreq = group_bin + bind_bin_addr
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
            else:
                assert address_family == socket.AF_INET
                mreq = group_bin + bind_bin_addr
                logger.debug(f"Joining multicast group {self.multicast_address} on {bind_address}; mreq={mreq}")
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            socket_binding = SddpSocketBinding(sock, unicast_addr=(bind_address, self.multicast_port))
            await self.add_socket_binding(socket_binding)

    async def finish_start(self) -> None:
        """Called after the socket is up and running.  Subclasses can override to do additional
           initialization."""
        self.collector_task = asyncio.create_task(self._run_collector_task())
        self.responder_task = asyncio.create_task(self._run_responder_task())

    async def wait_for_dependents_done(self) -> None:
        """Called after final_result has been awaited.  Subclasses can override to do additional
           cleanup."""
        try:
            if self.collector_task is not None:
                self.collector_task.cancel()
                await self.collector_task
                self.collector_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling collector task: {e}")

        try:
            if self.advertiser_task is not None:
                self.advertiser_task.cancel()
                await self.advertiser_task
                self.advertiser_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling advertiser task: {e}")

        try:
            if self.responder_task is not None:
                self.responder_task.cancel()
                await self.responder_task
                self.responder_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling responder task: {e}")

    async def _run_collector_task(self) -> None:
        logger.debug("Device collector task starting")
        try:
            async with SddpDatagramSubscriber(self) as subscriber:
                async for socket_binding, addr, datagram in subscriber.iter_datagrams():
                    logger.debug(f"Collector received datagram from {socket_binding} {addr}: {datagram}")
        except BaseException as e:
            logger.warning(f"Device collector task exiting with exception: {e}")
            raise
        logger.debug("Device collector task exiting")

    _responder_req_statement_re = re.compile(r'^SEARCH +(?P<pattern>[^ ]+) (?P<protocol>HTTP|SDDP)/(?P<version_major>[0-9]*)\.(?P<version_minor>[0-9]+) *$')
    async def _run_responder_task(self) -> None:
        logger.debug("Sddp responder task starting")
        try:
            async with SddpDatagramSubscriber(self) as subscriber:
                async for socket_binding, addr, datagram in subscriber.iter_datagrams():
                    m = self._responder_req_statement_re.match(datagram.statement_line)
                    if m:
                        statement_protocol = m.group('protocol')
                        if statement_protocol in ('HTTP', "SDDP"):
                            version_major: Optional[int] = None
                            version_minor: Optional[int] = None
                            try:
                                version_major = int(m.group('version_major'))
                            except ValueError:
                                pass
                            try:
                                version_minor = int(m.group('version_minor'))
                            except ValueError:
                                pass
                            if not version_major is None and not version_minor is None and version_major >= 1:
                                pattern = m.group('pattern')
                                # NOTE: in the future when SDDP protocol is documented, we can filter based on pattern
                                #       but for now we will always respond.
                                logger.debug(f"Sddp responder received SEARCH request from {addr} on {socket_binding}: pattern='{pattern}', protocol={statement_protocol}, version={version_major}.{version_minor}")
                                response = self.advertise_datagram.copy()
                                response.statement_line = f"{statement_protocol}/{version_major}.{version_minor} 200 OK"
                                if not 'From' in response:
                                    # Fill in the From header with the unicast address that applies to the interface on which the request was received
                                    unicast_ip, unicast_port = socket_binding.unicast_addr
                                    response['From'] = f"{unicast_ip}:{unicast_port}"
                                socket_binding.sendto(response, addr)
        except BaseException as e:
            logger.warning(f"Sddp responder task exiting with exception: {e}")
            raise
        logger.debug("Sddp responder task exiting")

if __name__ == "__main__":
  import logging

  async def amain() -> None:
        device_headers = {
            "Host": socket.gethostname(),
            "Type": "acme:TestServer",
            "Primary-Proxy": "test_server",
            "Proxies": "test_server",
            "Manufacturer": "Acme",
            "Model": "TestServer",
            "Driver": "test_server.c4z"          
        }
        server = SddpServer(device_headers=device_headers)
        await server.start()
        try:
            await asyncio.wait_for(asyncio.shield(server.wait_for_done()), timeout=2000.0)
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
