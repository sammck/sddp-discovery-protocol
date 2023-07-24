# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""
Package ssdp_discovery_protocol implements Control4's Simple Device Discovery Protocol (SDDP).

SDDP is a proprietary nonstandard protocol created by Control4 to discover
controllable devices on a local network. It is loosely based on the open Simple
Service Discovery Protocol (SSDP) defined by the UPnP Forum, and is often
confused with that protocol in online discussions. However, it differs from
SSDP in several ways, including the use of a different port number (1902 instead of 1900)
and a different message format.

SDDP responders are implemented in many home automation/media devices, including
projectors, TVs, AV receivers, smart speakers, curtain controllers, etc.

SDDP is not publicly documented by Control4, but the protocol has been partially
reverse-engineered--enough at least to discover devices and to implement simple device responders.

"""

from .version import __version__

from .internal_types import Jsonable, JsonableDict

from .exceptions import SddpError

from .sddp_datagram import SddpDatagram
from .sddp_socket import SddpSocket, SddpSocketBinding, SddpDatagramSubscriber
from .server import SddpServer, SddpAdvertisementInfo
from .client import SddpClient, SddpSearchRequest, SddpResponseInfo, DEFAULT_RESPONSE_WAIT_TIME
from .util import CaseInsensitiveDict
from .constants import SDDP_MULTICAST_ADDRESS, SDDP_PORT

__all__ = [
    '__version__',
    'Jsonable', 'JsonableDict',
    'SddpError',
    'SddpDatagram',
    'SddpSocket', 'SddpSocketBinding', 'SddpDatagramSubscriber',
    'SddpServer', 'SddpAdvertisementInfo',
    'SddpClient', 'SddpResponseInfo',
    'CaseInsensitiveDict',
    'DEFAULT_RESPONSE_WAIT_TIME',
    'SDDP_MULTICAST_ADDRESS', 'SDDP_PORT',
]
