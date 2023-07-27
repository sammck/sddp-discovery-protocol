# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""
SddpClient -- An SDDP client that can:

  1. Send a discovery request to a multicast UDP address (typically 239.255.255.250:1902)
  2. Receive and decode discovery response SddpDatagram's from remote nodes
  3. Collect and return responses received within a configurable timeout period
"""

from __future__ import annotations


import asyncio
from asyncio import Future
import socket
import sys
import re
import time
import datetime
from contextlib import asynccontextmanager

from .internal_types import *
from .pkg_logging import logger
from .constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

from .sddp_datagram import SddpDatagram
from .sddp_socket import SddpSocket, SddpSocketBinding, SddpDatagramSubscriber
from .util import get_local_ip_addresses, CaseInsensitiveDict

DEFAULT_RESPONSE_WAIT_TIME = 4.0
"""The default amount of time (in seconds) to wait for responses to come in."""

class SddpResponseInfo:
    socket_binding: SddpSocketBinding
    """The socket binding on which the response was received"""

    src_addr: HostAndPort
    """The source address of the response"""

    datagram: SddpDatagram
    """The response datagram"""

    sddp_version: str
    """The SDDP version string in the statement line (e.g. "1.0")"""

    status_code: int
    """The status code in the statement line (e.g. 200)"""

    status: str
    """The status string in the statement line (e.g. "OK")"""

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
            status_code: int,
            status: str
          ) -> None:
        self.socket_binding = socket_binding
        self.src_addr = src_addr
        self.datagram = datagram
        self.sddp_version = sddp_version
        self.status_code = status_code
        self.status = status
        self.monotonic_time = time.monotonic()
        self.utc_time = datetime.datetime.utcnow()

class SddpSearchRequest(
        AsyncContextManager['SddpSearchRequest'],
        AsyncIterable[SddpResponseInfo]
      ):
    """An object that manages a single search request on an SddpClient and all of the received responses
       within an AsyncContextManager/AsyncInterable interface."""

    _response_statement_re = re.compile(r'^SDDP/(?P<version_major>[0-9]*)\.(?P<version_minor>[0-9]+) +(?P<status_code>[0-9]+) +(?P<status>.*[^ ]) *$')

    sddp_client: SddpClient
    search_pattern: str
    include_error_responses: bool

    dg_subscriber: SddpDatagramSubscriber
    response_wait_time: float
    max_responses: int
    end_time: float = 0.0
    filter_headers: Optional[CaseInsensitiveDict[Union[str, int]]] = None

    def __init__(
            self,
            sddp_client: SddpClient,
            search_pattern: str="*",
            response_wait_time: Optional[float]=None,
            max_responses: int=0,
            include_error_responses: bool=False,
            filter_headers: Optional[Mapping[str, Union[str, int]]]=None
          ):
        """Create an async context manager/iterable that sends a multicast search request and returns the responses
        as they arrive.

        Parameters:
            sddp_client:             The SddpClient instance to use for sending the search request and receiving responses.
            search_pattern:          The search pattern to use. Defaults to "*" (all devices).
            response_wait_time:      The amount of time (in seconds) to wait for responses to come in. Defaults to
                                        sddp_client.response_wait_time.
            max_responses:           The maximum number of responses to return. If 0 (the default), all responses received
                                        within response_wait_time will be returned.
            include_error_responses: If True, responses with a non-200 status code will be included in the results.
                                        Defaults to False.
            filter_headers:          A mapping of headers to values. If specified, only responses that have all of the
                                        specified headers with the specified values will be included in the results. Defaults
                                        to None.

        Usage:
            async with SddpSearchRequest(sddp_client, ...) as search_request:
                async for response in search_request:
                    print(response.datagram.headers)
                    # It is possible to break out of the loop early if desired; e.g., if you got the response you were looking for..
        """
        self.sddp_client = sddp_client
        self.search_pattern = search_pattern
        self.response_wait_time = sddp_client.response_wait_time if response_wait_time is None else response_wait_time
        self.max_responses = max_responses
        self.include_error_responses = include_error_responses
        self.dg_subscriber = SddpDatagramSubscriber(self.sddp_client)
        self.filter_headers = None if filter_headers is None else CaseInsensitiveDict(filter_headers)

    async def __aenter__(self) -> SddpSearchRequest:
        # It is important that we start the subscriber before we send the search request so that we don't miss any responses.
        await self.dg_subscriber.__aenter__()
        try:
            for socket_binding in self.sddp_client.socket_bindings:
                search_datagram = SddpDatagram(f"SEARCH {self.search_pattern} SDDP/1.0")
                search_datagram['Host'] = f"{socket_binding.unicast_addr[0]}:{socket_binding.unicast_addr[1]}"
                socket_binding.sendto(search_datagram, (self.sddp_client.multicast_address, self.sddp_client.multicast_port))
            self.end_time = time.monotonic() + self.response_wait_time
        except BaseException as e:
            # A call to __aenter__ that raises an exception will not be paired with a call to __aexit__; since we successfully called __aenter__
            # on the dg_subscriber, we need to call __aexit__ on it to ensure that it is cleaned up properly.
            await self.dg_subscriber.__aexit__(type(e), e, e.__traceback__)
            raise
        return self

    async def __aexit__(
            self,
            exc_type: Optional[type[BaseException]],
            exc: Optional[BaseException],
            tb: Optional[TracebackType]
      ) -> bool:
        return await self.dg_subscriber.__aexit__(exc_type, exc, tb)

    async def iter_responses(self) -> AsyncIterator[SddpResponseInfo]:
        n = 0
        while True:
            if self.max_responses > 0 and n >= self.max_responses:
                break
            remaining_time = self.end_time - time.monotonic()
            if remaining_time <= 0.0:
                break
            try:
                resp_tuple = await asyncio.wait_for(self.dg_subscriber.receive(), remaining_time)
            except asyncio.TimeoutError:
                break
            if resp_tuple is None:
                break
            socket_binding, addr, datagram = resp_tuple
            m = self._response_statement_re.match(datagram.statement_line)
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
                    status_code_str = m.group('status_code')
                    status_code: Optional[int] = None
                    try:
                        status_code = int(status_code_str)
                    except ValueError:
                        pass
                    if not status_code is None:
                        status = m.group('status')
                        info = SddpResponseInfo(socket_binding, addr, datagram, f"{version_major}.{version_minor}", status_code, status)
                        logger.debug(f"Received SDDP response from {addr} on {socket_binding}: version={info.sddp_version}, status_code={status_code}, status={status}, headers={datagram.headers}")
                        if self.include_error_responses or status_code == 200:
                            if self.filter_headers is None or all(datagram.headers.get(key, None) == value for key, value in self.filter_headers.items()):
                                n += 1
                                yield info

    def __aiter__(self) -> AsyncIterator[SddpResponseInfo]:
        return self.iter_responses()


class SddpClient(SddpSocket, AsyncContextManager['SddpClient']):
    """
    An SDDP client that can:

      1. Send a discovery request to a multicast UDP address (typically 239.255.255.250:1902)
      2. Receive and decode discovery response SddpDatagram's from remote nodes
      3. Collect and return responses received within a configurable timeout period
    """
    response_wait_time: float
    """The amount of time (in seconds) to wait for all responses to come in. By default,
       this is set to 3.0 seconds."""

    multicast_address: str = SDDP_MULTICAST_ADDRESS
    """The multicast address to send requests to."""

    multicast_port: int = SDDP_PORT
    """The multicast port to send requests to."""

    bind_addresses: List[str]
    """The local IP addresses to bind to. If None, all local IP addresses will be used."""

    include_loopback: bool = False
    """If True, loopback addresses will be included in the list of local IP addresses to bind to."""

    def __init__(
            self,
            search_pattern: str="*",
            response_wait_time: float=DEFAULT_RESPONSE_WAIT_TIME,
            multicast_address: str=SDDP_MULTICAST_ADDRESS,
            multicast_port: int=SDDP_PORT,
            bind_addresses: Optional[Iterable[str]]=None,
            include_loopback: bool = False
          ) -> None:
        super().__init__()
        self.search_pattern = search_pattern
        self.response_wait_time = response_wait_time
        self.multicast_address = multicast_address
        self.multicast_port = multicast_port
        self.include_loopback = include_loopback
        if bind_addresses is None:
            bind_addresses = get_local_ip_addresses(include_loopback=self.include_loopback)
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
        logger.debug(f"Creating socket bindings to {self.bind_addresses}")
        for bind_address in self.bind_addresses:
            sock = socket.socket(address_family, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_address, 0))
            bind_port = sock.getsockname()[1]
            if sys.platform not in ( 'win32', 'cygwin' ):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            socket_binding = SddpSocketBinding(sock, unicast_addr=sock.getsockname())
            await self.add_socket_binding(socket_binding)

    async def finish_start(self) -> None:
        """Called after the socket is up and running.  Subclasses can override to do additional
           initialization."""
        pass

    async def wait_for_dependents_done(self) -> None:
        """Called after final_result has been awaited.  Subclasses can override to do additional
           cleanup."""
        pass

    def search(
            self,
            search_pattern: str="*",
            response_wait_time: Optional[float]=None,
            max_responses: int=0,
            include_error_responses: bool=False,
            filter_headers: Optional[Mapping[str, str]]=None,
          ) -> SddpSearchRequest:
        """Create an async context manager/iterable that sends a multicast search request and returns the responses
           as they arrive.

        Parameters:
            search_pattern:          The search pattern to use. Defaults to "*" (all devices).
            response_wait_time:      The amount of time (in seconds) to wait for responses to come in. Defaults to
                                        sddp_client.response_wait_time.
            max_responses:           The maximum number of responses to return. If 0 (the default), all responses received
                                        within response_wait_time will be returned.
            include_error_responses: If True, responses with a non-200 status code will be included in the results.
                                        Defaults to False.
            filter_headers:          A mapping of headers to values. If specified, only responses that have all of the
                                        specified headers with the specified values will be included in the results. Defaults
                                        to None.

        Usage:
            async with sddp_client.search(...) as search_request:
                async for response in search_request:
                    print(response.datagram.headers)
                    # It is possible to break out of the loop early if desired; e.g., if you got the response you were looking for..
        """
        return SddpSearchRequest(
                self,
                search_pattern=search_pattern,
                response_wait_time=response_wait_time,
                max_responses=max_responses,
                include_error_responses=include_error_responses,
                filter_headers=filter_headers,
              )

    async def simple_search(
            self,
            search_pattern: str="*",
            response_wait_time: Optional[float]=None,
            max_responses: int=0,
            include_error_responses: bool=False,
            filter_headers: Optional[Mapping[str, str]]=None,
          ) -> List[SddpResponseInfo]:
        """A simple search that creates a search request, waits for a fixed time for all responses to come in,
           and returns the responses. Does not allow for early termination of the search when
           a desired response is received.

           Early out/incremental results can be obtained by using the search() method.

        Parameters:
            sddp_client:             The SddpClient instance to use for sending the search request and receiving responses.
            search_pattern:          The search pattern to use. Defaults to "*" (all devices).
            response_wait_time:      The amount of time (in seconds) to wait for responses to come in. Defaults to
                                        sddp_client.response_wait_time.
            max_responses:           The maximum number of responses to return. If 0 (the default), all responses received
                                        within response_wait_time will be returned.
            include_error_responses: If True, responses with a non-200 status code will be included in the results.
                                        Defaults to False.
            filter_headers:          A mapping of headers to values. If specified, only responses that have all of the
                                        specified headers with the specified values will be included in the results. Defaults
                                        to None.
        """
        results: List[SddpResponseInfo] = []
        async with self.search(
                search_pattern=search_pattern,
                response_wait_time=response_wait_time,
                max_responses=max_responses,
                include_error_responses=include_error_responses,
                filter_headers=filter_headers,
              ) as search_request:
            async for response in search_request:
                results.append(response)
        return results

    async def __aenter__(self) -> SddpClient:
        await super().__aenter__()
        return self
