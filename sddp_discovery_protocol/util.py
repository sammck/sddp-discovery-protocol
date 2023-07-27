#
# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""
Simple utility functions used by this package
"""

from __future__ import annotations

from typing_extensions import SupportsIndex

import netifaces
import sys
import socket
import ipaddress
from ipaddress import IPv4Address, IPv6Address

from sddp_discovery_protocol.internal_types import *

from email.parser import BytesHeaderParser
from email.message import Message as EmailParserMessage
from email.header import Header as EmailParserHeader
from requests.structures import CaseInsensitiveDict

def split_bytes_at_lf_or_crlf(data: bytes, maxsplit: SupportsIndex = -1) -> List[bytes]:
    """Split a byte string at LF or CRLF.

    If maxsplit is given, at most maxsplit splits are done.

    Returns a List[bytes] representing the delimiteds lines with the delimiters removed.
    """
    parts = data.split(b'\n', maxsplit)
    if len(parts) > 1:
        for i, part in enumerate(parts[:-1]):
            if part.endswith(b'\r'):
                parts[i] = part[:-1]
    return parts

def split_headers_and_body(data: bytes) -> Tuple[bytes, bytes]:
    """Spits a byte string with HTTP headers and an optional body into the headers and the body.

    A relaxed interpretation of '\n' as a line delimiter is accepted even though '\r\n' is required
    by the standard.

    Returns a Tuple[headers: bytes, body: bytes]. If there is no body, b'' is returned for the body.
    """
    delims = [b'\n\r\n', b'\n\n']
    first_i = -1
    first_nb = 0

    for delim in delims:
        i = data.find(delim)
        if i != -1:
            if first_i == -1 or i < first_i:
                first_i = i
                first_nb = len(delim)
    if first_i == -1:
        headers, body = data, b''
    else:
        headers, body = data[:first_i], data[first_i + first_nb:]
        if headers.endswith(b'\r'):
            headers = headers[:-1]

    return (headers, body)

def parse_http_headers(data: bytes) -> Tuple[CaseInsensitiveDict[str], bytes]:
    """Parse HTTP-style headers out of a byte string. Also returns the body of the message, if any.

    A relaxed interpretation of '\n' as a line delimiter is accepted even though '\r\n' is required
    by the standard.  The final line of the headers does not need to be terminated by a newline. If
    there is a body, it is separated from the headers with '\r\n\r\n', '\n\n', '\r\n\n', or '\r\n\n'.

    It is assumed that any preceding statement line (e.g., "HTTP/1.1 200 OK\r\n") has already been removed.

    No decoding of header values is performed--e.g., quoted strings, base64, etc. are not decoded.

    Returns a tuple of (headers: CaseInsensitiveDict[str], body: bytes).
    """

    headers_data, body = split_headers_and_body(data)
    i = 0

    # Normalize the header line endings to '\r\n'
    while True:
        i = headers_data.find(b'\n', i)
        if i == -1:
            break
        if i == 0 or headers_data[i - 1] != ord('\r'):
            headers_data = headers_data[:i] + b'\r' + headers_data[i:]
            i += 2
        else:
            i += 1

    msg: EmailParserMessage = BytesHeaderParser().parsebytes(headers_data)
    headers: CaseInsensitiveDict[str] = CaseInsensitiveDict(msg.items())
    return (headers, body)

def encode_http_header(name: str, value: str) -> bytes:
    """Encodes a raw HTTP header name/value pair into a byte string.

    RFC 2822 line wrapping is provided.
    The result is terminated with '\r\n'.
    """
    h = EmailParserHeader(value, header_name=name)
    return name.encode() + b': ' + h.encode(linesep='\r\n').encode() + b'\r\n'

def get_local_ip_addresses_and_interfaces(
        address_family: Union[socket.AddressFamily, int]=socket.AF_INET,
        include_loopback: bool=True
    ) -> List[Tuple[str, str]]:
    """Returns a list of Tuple[ip_address: str, interface_name: str] for the IP addresses of the local host
       in a requested address family. The result is sorted in a way that attempts to place the "preferred"
       canonical IP address first in the list, according to the following scheme:
           1. Addresses on the default gateway interface precede all other addresses.
           2. Non-loopback addresses precede loopback addresses.
           3. IPV4 addresses that begin with 172. follow other IPV4 addresses. This is a hack to
              deprioritize local docker network addresses.
    """
    result_with_priority: List[Tuple[int, str, str]] = []
    assert int(address_family) in (int(socket.AF_INET), int(socket.AF_INET6))
    is_ipv6 = int(address_family) == int(socket.AF_INET6)
    _, default_gateway_ifname = get_default_ip_gateway(address_family)
    netiface_family = netifaces.AF_INET6 if is_ipv6 else netifaces.AF_INET
    for ifname in netifaces.interfaces():
        ifinfo = netifaces.ifaddresses(ifname)
        if netiface_family in ifinfo:
            for addrinfo in ifinfo[netiface_family]:
              ip_str = addrinfo['addr']
              assert isinstance(ip_str, str)
              if ifname == default_gateway_ifname:
                  priority = 0
              elif is_ipv6 and IPv6Address(ip_str).is_loopback:
                  if not include_loopback:
                      continue
                  priority = 3
              elif not is_ipv6 and IPv4Address(ip_str).is_loopback:
                  if not include_loopback:
                      continue
                  priority = 3
              elif not is_ipv6 and ip_str.startswith('172.'):
                  priority = 2
              else:
                  priority = 1

              result_with_priority.append((priority, ip_str, ifname))
    return [ (ip, ifname) for _, ip, ifname in sorted(result_with_priority)]

def get_local_ip_addresses(address_family: Union[socket.AddressFamily, int]=socket.AF_INET, include_loopback: bool=True) -> List[str]:
    """Returns a List[ip_address: str] for the IP addresses of the local host
       in a requested address family. The result is sorted in a way that attempts to place the "preferred"
       canonical IP address first in the list, according to the following scheme:
           1. Addresses on the default gateway interface precede all other addresses.
           2. Non-loopback addresses precede loopback addresses.
           3. IPV4 addresses that begin with 172. follow other IPV4 addresses. This is a hack to
              deprioritize local docker network addresses."""
    return [ ip for ip, _ in get_local_ip_addresses_and_interfaces(address_family, include_loopback=include_loopback)]

def get_default_ip_gateway(address_family: socket.AddressFamily | int=socket.AF_INET) -> Tuple[Optional[str], Optional[str]]:
    """Returns the (gateway_ip_address: str, gateway_interface_name: str) for the default IP gateway in the
       requested family, if any.
       returns (None, None) if there is no default gateway in the requested family."""
    assert int(address_family) in (int(socket.AF_INET), int(socket.AF_INET6))
    netiface_family = netifaces.AF_INET if int(address_family) == int(socket.AF_INET) else netifaces.AF_INET6
    gws = netifaces.gateways()
    if "default" in gws:
        default_gateway_infos = gws["default"]
        if netiface_family in default_gateway_infos:
            gw_ip, gw_interface_name = default_gateway_infos[netiface_family][:2]
            return (gw_ip, gw_interface_name)
    return (None, None)

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Parse HTTP-style headers out of a byte string.")
    parser.add_argument("input", type=str, help="Input file to read from. If '-', read from stdin.")
    args = parser.parse_args()

    if args.input == '-':
        data = sys.stdin.buffer.read()
    else:
        with open(args.input, 'rb') as f:
            data = f.read()

    statement_and_remainder = split_bytes_at_lf_or_crlf(data, 1)
    print("Statement and remainder: ", statement_and_remainder, file=sys.stderr)
    statement_line = statement_and_remainder[0].decode('utf-8')
    remainder = b'' if len(statement_and_remainder) < 2 else statement_and_remainder[1]

    headers, body = parse_http_headers(remainder)
    print(f"Statement line: {statement_line}")
    print(f"Headers: {headers}")
    print(f"Body: {body!r}")
