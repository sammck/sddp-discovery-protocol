#
# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

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
import time
import datetime

from sddp_discovery_protocol.internal_types import *
from .pkg_logging import logger
from .constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

from .sddp_datagram import SddpDatagram
from .sddp_socket import SddpSocket, SddpSocketBinding, SddpDatagramSubscriber
from .util import get_local_ip_addresses

DEFAULT_MAX_AGE = 1800

IP_MULTICAST_ALL = 49
IPV6_MULTICAST_ALL = 41

class SddpAdvertisementInfo:
    socket_binding: SddpSocketBinding
    """The socket binding on which the advertisement was received"""

    src_addr: HostAndPort
    """The source address of the advertisement"""

    datagram: SddpDatagram
    """The advertisement datagram"""

    sddp_version: str
    """The SDDP version string in the statement line (e.g. "1.0")"""

    monotonic_time: float
    """The local time (in seconds) since an arbitrary point in the past at which
       the advertisement was received, as returned by time.monotonic(). This
       value is useful for calculating the age of the advertisement and expiring
       after Max-Age seconds."""

    utc_time: datetime.datetime
    """The UTC time at which the advertisement was received, as returned by
        datetime.datetime.utcnow()."""

    def __init__(
            self,
            socket_binding: SddpSocketBinding,
            src_addr: HostAndPort,
            datagram: SddpDatagram,
            sddp_version: str,
          ) -> None:
        self.socket_binding = socket_binding
        self.src_addr = src_addr
        self.datagram = datagram
        self.sddp_version = sddp_version
        self.monotonic_time = time.monotonic()
        self.utc_time = datetime.datetime.utcnow()

SddpServerNotifyHandler = Callable[[SddpAdvertisementInfo], Awaitable[None]]
"""A callback for received SDDP advertisements."""
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
    """The IP addresses to bind to. If None, all local IP addresses will be used."""

    include_loopback: bool = False
    """If True, loopback addresses will be included in the list of local IP addresses to bind to."""

    notify_handlers: Dict[int, SddpServerNotifyHandler]
    """A set of handlers that will be called when an advertisement notification is received from a remote host,
       indexed by ID number."""

    i_next_notify_handler: int = 0
    """The next notify handler ID to assign."""

    def __init__(
            self,
            device_headers: Optional[Mapping[str, str | int | float | None]]=None,
            advertise_interval: Optional[float]=None,
            respond_to_queries: bool=True,
            multicast_address: str=SDDP_MULTICAST_ADDRESS,
            multicast_port: int=SDDP_PORT,
            bind_addresses: Optional[Iterable[str]]=None,
            include_loopback: bool = False
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
        self.include_loopback = include_loopback
        if bind_addresses is None:
            bind_addresses = get_local_ip_addresses(include_loopback=self.include_loopback)
        self.bind_addresses = list(bind_addresses)
        self.notify_handlers = {}

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
        logger.debug(f"Creating socket bindings to {self.multicast_address}:{self.multicast_port} from {self.bind_addresses}")
        for bind_address in self.bind_addresses:
            sock = socket.socket(address_family, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sys.platform not in ( 'win32', 'cygwin' ):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            # On Linux, disabling IP_MULTICAST_ALL ensures that each socket only receives
            # multicast packets sent to the multicast address on the interface that the
            # socket is bound to.  Without doing this, every multicast is received by all sockets
            # bound to 0.0.0.0:<port> even if IP_ADD_MEMBERSHIP for the socket includes a filter for
            # the bind address. If there are multiple bound sockets, This would result in duplicate
            # packets being received by subscribers, with incorrect SddpBoundSocket values.
            if sys.platform in ('linux', 'linux2'):
                logger.debug(f"Disabling IP_MULTICAST_ALL on socket {bind_address}")
                sock.setsockopt(socket.IPPROTO_IP, IPV6_MULTICAST_ALL if is_ipv6 else IP_MULTICAST_ALL, 0)
            # Multicast listeners MUST bind to 0.0.0.0:<port> or [::]:<port> to receive multicast packets
            sock.bind(('', self.multicast_port))
            bind_bin_addr = socket.inet_pton(address_family, bind_address)
            if is_ipv6:
                assert address_family == socket.AF_INET6
                mreq = group_bin + bind_bin_addr
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
            else:
                assert address_family == socket.AF_INET
                mreq = group_bin + bind_bin_addr
                logger.debug(f"Joining multicast group {self.multicast_address} on {bind_address}; mreq={mreq!r}")
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            socket_binding = SddpSocketBinding(sock, unicast_addr=(bind_address, self.multicast_port))
            await self.add_socket_binding(socket_binding)

    def add_notify_handler(self, handler: SddpServerNotifyHandler) -> int:
        """Adds a handler to be called when an advertisement notification is received from a remote host."""
        i = self.i_next_notify_handler
        self.i_next_notify_handler += 1
        self.notify_handlers[i] = handler
        return i

    def remove_notify_handler(self, i: int) -> None:
        """Removes a previously added notify handler."""
        del self.notify_handlers[i]

    async def finish_start(self) -> None:
        """Called after the socket is up and running.  Subclasses can override to do additional
           initialization."""
        self.collector_task = asyncio.create_task(self._run_collector_task())
        self.responder_task = asyncio.create_task(self._run_responder_task())
        if self.advertise_interval > 0.0:
            self.advertiser_task = asyncio.create_task(self._run_advertiser_task())

    async def wait_for_dependents_done(self) -> None:
        """Called after final_result has been awaited.  Subclasses can override to do additional
           cleanup."""
        try:
            if self.collector_task is not None:
                self.collector_task.cancel()
                try:
                    await self.collector_task
                except BaseException:
                    pass
                self.collector_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling collector task: {e}")

        try:
            if self.advertiser_task is not None:
                self.advertiser_task.cancel()
                try:
                    await self.advertiser_task
                except BaseException:
                    pass
                self.advertiser_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling advertiser task: {e}")

        try:
            if self.responder_task is not None:
                self.responder_task.cancel()
                try:
                    await self.responder_task
                except BaseException:
                    pass
                self.responder_task = None
        except asyncio.CancelledError:
            pass
        except BaseException as e:
            logger.warning(f"Exception while cancelling responder task: {e}")

    _collector_notify_statement_re = re.compile(r'^NOTIFY +ALIVE +SDDP/(?P<version_major>[0-9]*)\.(?P<version_minor>[0-9]+) *$')
    async def _run_collector_task(self) -> None:
        logger.debug("Device collector task starting")
        try:
            async with SddpDatagramSubscriber(self) as subscriber:
                async for socket_binding, addr, datagram in subscriber.iter_datagrams():
                    m = self._collector_notify_statement_re.match(datagram.statement_line)
                    if m:
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
                            info = SddpAdvertisementInfo(socket_binding, addr, datagram, f"{version_major}.{version_minor}")
                            logger.debug(f"Collector received NOTIFY from {addr} on {socket_binding}: version={info.sddp_version}, headers={datagram.headers}")
                            for handler in self.notify_handlers.values():
                                await handler(info)
        except asyncio.CancelledError:
            logger.debug("Device collector task cancelled; exiting")
            raise
        except BaseException as e:
            logger.info(f"Device collector task exiting with exception: {e}")
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
                                assert not self.advertise_datagram is None
                                response = self.advertise_datagram.copy()
                                response.statement_line = f"{statement_protocol}/{version_major}.{version_minor} 200 OK"
                                if not 'From' in response:
                                    # Fill in the From header with the unicast address that applies to the interface on which the request was received
                                    unicast_ip, unicast_port = socket_binding.unicast_addr
                                    response['From'] = f"{unicast_ip}:{unicast_port}"
                                socket_binding.sendto(response, addr)
        except asyncio.CancelledError:
            logger.debug("SddpResponser task cancelled; exiting")
            raise
        except BaseException as e:
            logger.info(f"Sddp responder task exiting with exception: {e}")
            raise
        logger.debug("Sddp responder task exiting")

    async def _run_advertiser_task(self) -> None:
        logger.debug(f"Sddp advertiser task starting, advertising every {self.advertise_interval} seconds")
        assert self.advertise_interval > 0.0
        try:
            while not self.final_result.done():
                for socket_binding in self.socket_bindings:
                    assert not self.advertise_datagram is None
                    advertise_datagram = self.advertise_datagram.copy()
                    if not 'From' in advertise_datagram:
                        # Fill in the From header with the unicast address that applies to the interface on which the advertisement is being sent
                        unicast_ip, unicast_port = socket_binding.unicast_addr
                        advertise_datagram['From'] = f"{unicast_ip}:{unicast_port}"
                    socket_binding.sendto(advertise_datagram, (self.multicast_address, self.multicast_port))
                try:
                    await asyncio.wait_for(asyncio.shield(self.final_result), timeout=self.advertise_interval)
                except:
                    pass
        except asyncio.CancelledError:
            logger.debug("Sddp advertiser task cancelled; exiting")
            raise
        except BaseException as e:
            logger.info(f"Sddp advertiser task exiting with exception: {e}")
            raise
        logger.debug("Sddp advertiser task exiting")
