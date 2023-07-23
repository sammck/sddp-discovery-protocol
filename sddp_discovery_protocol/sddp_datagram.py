#
# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""
Abstraction of a Datagram packet used in the SDDP protocol.
"""

from __future__ import annotations

from sddp_discovery_protocol.internal_types import *
from .pkg_logging import logger

from .constants import SDDP_PORT

from .util import (
    CaseInsensitiveDict,
    split_bytes_at_lf_or_crlf,
    parse_http_headers,
    encode_http_header,
)

import json

HeaderValue = Union[str, int, float]
NullableHeaderValue = Optional[HeaderValue]

class SddpDatagram(MutableMapping[str, HeaderValue]):
    """Wrapper for a raw SDDP datagram.

    This class provides parsing and formatting of the HTTP-like packets, a dict-like
    interface to the headers (including unquoting strings), and a few other convenient
    properties.
    """

    _raw_data: bytes
    """The raw UDP datagram contents"""

    _statement_line: str
    """The first line of the datagram; e.g., "SDDP/1.0 200 OK,
       "NOTIFY ALIVE SDDP/1.0", etc."""

    _raw_headers: CaseInsensitiveDict[str]
    """The undecoded headers as a CaseInsensitiveDict[str]. Quoted strings are not unquoted."""

    _body: bytes
    """The body of the datagram, if any. If there is no body, b'' is returned."""

    _headers: CaseInsensitiveDict[HeaderValue]
    """The decoded headers as a CaseInsensitiveDict[HeaderValue]. Quoted strings are unquoted
       using JSON syntax. headers that are not valid JSON are omitted"""

    def __init__(
            self,
            statement: Optional[str]=None,
            headers: Optional[Mapping[str, NullableHeaderValue]]=None,
            body: Optional[bytes]=None,
            raw_data: Optional[bytes]=None,
            copy_from: Optional[SddpDatagram]=None
          ):
        if copy_from is not None:
            assert statement is None and headers is None and body is None and raw_data is None
            self._raw_data = copy_from._raw_data
            self._statement_line = copy_from._statement_line
            self._raw_headers = copy_from._raw_headers.copy()
            self._headers = copy_from._headers.copy()
            self._body = copy_from._body
            return
        self._raw_headers = CaseInsensitiveDict()
        self._headers = CaseInsensitiveDict()
        if raw_data is None:
            if statement is None:
                raise ValueError("Either statement or raw_data must be provided")
            assert isinstance(statement, str)
            self._statement_line = statement
            self._body = b'' if body is None else body
            if not headers is None:
                self._update_no_rebuild(headers)
            self._rebuild_raw_data()
        else:
            assert isinstance(raw_data, bytes)
            if not (statement is None and headers is None and body is None):
                raise ValueError("If raw_data is provided, statement, headers, and body must be None")
            self.raw_data = raw_data
            # derived attributes are set by the setter for raw_data


    def __str__(self) -> str:
        return f"SddpDatagram('{self._statement_line}', headers={self._raw_headers}, body={self._body!r})"

    def __repr__(self) -> str:
        return str(self)

    @property
    def raw_data(self) -> bytes:
        """The raw UDP datagram contents"""
        return self._raw_data

    @raw_data.setter
    def raw_data(self, value: bytes) -> None:
        """Set the raw UDP datagram contents, and recompute headers."""
        assert isinstance(value, bytes)
        self._raw_data = value
        statement_and_remainder = split_bytes_at_lf_or_crlf(self.raw_data, 1)
        self._statement_line = statement_and_remainder[0].decode('utf-8')
        headers_and_body = b'' if len(statement_and_remainder) == 0 else statement_and_remainder[1]
        self._raw_headers, self._body = parse_http_headers(headers_and_body)
        self._rebuild_headers()

    @property
    def statement_line(self) -> str:
        """The first line of the datagram; e.g., "SDDP/1.0 200 OK,
           "NOTIFY ALIVE SDDP/1.0", etc."""
        return self._statement_line

    @statement_line.setter
    def statement_line(self, value: str) -> None:
        """Set the first line of the datagram; e.g., "SDDP/1.0 200 OK,
           "NOTIFY ALIVE SDDP/1.0", etc."""
        assert isinstance(value, str)
        self._statement_line = value
        self._rebuild_raw_data()

    @property
    def body(self) -> bytes:
        """The body of the datagram, if any. If there is no body, b'' is returned."""
        return self._body

    @body.setter
    def body(self, value: Optional[bytes]) -> None:
        """Set the body of the datagram, and update the raw data."""
        if value is None:
            self._body = b''
        else:
            assert isinstance(value, bytes)
            self._body = value
        self._rebuild_raw_data()

    def clear_headers(self) -> None:
        """Clear all headers."""
        self._headers.clear()
        self._raw_headers.clear()
        self._rebuild_raw_data()

    def update_raw_headers(
            self,
            other: Union[Mapping[str, Optional[str]], Iterable[Tuple[str, Optional[str]]]]=(),
            /,
            **kwargs: Optional[str]
          ) -> None:
        self._update_raw_headers_no_rebuild(other, **kwargs)
        self._rebuild_raw_data()

    @property
    def raw_headers(self) -> CaseInsensitiveDict[str]:
        """The undecoded headers as a CaseInsensitiveDict[str]. Quoted strings are not unquoted."""
        return self._raw_headers

    @raw_headers.setter
    def raw_headers(self, value: Optional[Mapping[str, str]]) -> None:
        """Set all of the raw headers from a dict, and updates the decoded headers and raw data as well."""
        if value is None:
            self.clear_headers()
        else:
            assert isinstance(value, Mapping)
            self._raw_headers.clear()
            self.update_raw_headers(value)

    def clear_decoded_headers(self) -> None:
        """Clear all decoded headers. Raw headers that were not valid JSON are left intact."""
        self._clear_decoded_headers_no_rebuild()
        self._rebuild_raw_data()

    @property
    def headers(self) -> CaseInsensitiveDict[HeaderValue]:
        """The decoded headers as a CaseInsensitiveDict[HeaderValue]. Quoted strings are unquoted
           using JSON syntax. headers that are not valid JSON are omitted"""
        return self._headers

    @headers.setter
    def headers(self, value: Optional[Mapping[str, NullableHeaderValue]]) -> None:
        self._clear_decoded_headers_no_rebuild()
        if value is not None:
            self.update(value)

    def set_raw_header(self, name: str, value: Optional[str]) -> None:
        """Set a raw undecoded header value, and updates the decoded header as well.
           If value is None, the header is removed.

           `name` is case-insensitive, but the case of the header name is preserved
           and updated to reflect the provided value.

           The raw packet byte string is updated to reflect the new header value.
        """
        self._set_raw_header_no_rebuild(name, value)
        self._rebuild_raw_data()

    def set_header(self, name: str, value: NullableHeaderValue) -> None:
        """Set a decoded header value, and updates the raw header as well.
           If value is None, the header is removed.

           `name` is case-insensitive, but the case of the header name is preserved
           and updated to reflect the provided value.

           The raw packet byte string is updated to reflect the new header value.
        """
        self._set_header_no_rebuild(name, value)
        self._rebuild_raw_data()

    def del_header(self, name: str) -> None:
        """Delete a decoded header value if it exists, and deletes the raw header as well.
           `name` is case-insensitive.
           If the header does not exist, this is a no-op.
           The raw packet byte string is updated to reflect the removed header.
        """
        self._del_header_no_rebuild(name)
        self._rebuild_raw_data()

    @property
    def hdr_from(self) -> Optional[HostAndPort]:
        """Returns the "From" header as a HostAndPort.

        Returns None if there is no From header or it is not a valid host/port string.
        """
        from_val = self.headers.get("From")
        if not isinstance(from_val, str):
            return None
        parts = from_val.split(':', 1)
        host = parts[0]
        if len(parts) < 2:
            port = SDDP_PORT
        else:
            try:
                port = int(parts[1])
            except ValueError:
                return None
        return (host, port)

    @hdr_from.setter
    def hdr_from(self, value: Optional[HostAndPort]) -> None:
        """Set the "From" header to a HostAndPort.

        If value is None, the header is removed.
        """
        if value is None:
            self.del_header("From")
        else:
            self.set_header("From", f"{value[0]}:{value[1]}")

    @property
    def hdr_host(self) -> Optional[str]:
        """Returns the "Host" header as a str.

        Returns None if there is no valid Host header.
        """
        result = self.headers.get("Host")
        if not isinstance(result, str):
            return None
        return result

    @hdr_host.setter
    def hdr_host(self, value: Optional[str]) -> None:
        """Set the "Host" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Host", value)

    @property
    def hdr_max_age(self) -> Optional[int]:
        """Returns the the "Max-Age" header as an int.

        Returns None if there is no valid Max-Age header.
        """
        result = self.headers.get("Max-Age")
        if not isinstance(result, int):
            return None
        return result

    @hdr_max_age.setter
    def hdr_max_age(self, value: Optional[int]) -> None:
        """Set the "Max-Age" header to a int.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, int)
        self.set_header("Max-Age", value)

    @property
    def hdr_type(self) -> Optional[str]:
        """Returns the "Type" header as a str.

        Returns None if there is no valid Type header.
        """
        result = self.headers.get("Type")
        if not isinstance(result, str):
            return None
        return result

    @hdr_type.setter
    def hdr_type(self, value: Optional[str]) -> None:
        """Set the "Type" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Type", value)

    @property
    def hdr_primary_proxy(self) -> Optional[str]:
        """Returns the "Primary-Proxy" header as a str.

        Returns None if there is no valid Primary-Proxy header.
        """
        result = self.headers.get("Primary-Proxy")
        if not isinstance(result, str):
            return None
        return result

    @hdr_primary_proxy.setter
    def hdr_primary_proxy(self, value: Optional[str]) -> None:
        """Set the "Primary-Proxy" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Primary-Proxy", value)

    @property
    def hdr_proxies(self) -> Optional[List[str]]:
        """Returns the "Proxies" header as a List[str].

        Returns None if there is no valid Proxies header.
        """
        result = self.headers.get("Proxies")
        if not isinstance(result, str):
            return None
        rlist = result.split(',')
        if len(rlist) == 1 and rlist[0] == '':
            rlist = []
        return rlist

    @hdr_proxies.setter
    def hdr_proxies(self, value: Optional[Iterable[str]]) -> None:
        """Set the "Proxies" header to comma-delimited list of strings.

        If value is None, the header is removed.
        """
        if value is None:
            svalue = None
        else:
            assert all(isinstance(x, str) for x in value)
            svalue = ','.join(value)
        self.set_header("Proxies", svalue)

    @property
    def hdr_manufacturer(self) -> Optional[str]:
        """Returns the "Manufacturer" header as a str.

        Returns None if there is no valid Manufacturer header.
        """
        result = self.headers.get("Manufacturer")
        if not isinstance(result, str):
            return None
        return result

    @hdr_manufacturer.setter
    def hdr_manufacturer(self, value: Optional[str]) -> None:
        """Set the "Manufacturer" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Manufacturer", value)

    @property
    def hdr_model(self) -> Optional[str]:
        """Returns the "Model" header as a str.

        Returns None if there is no valid Model header.
        """
        result = self.headers.get("Model")
        if not isinstance(result, str):
            return None
        return result

    @hdr_model.setter
    def hdr_model(self, value: Optional[str]) -> None:
        """Set the "Model" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Model", value)

    @property
    def hdr_driver(self) -> Optional[str]:
        """Returns the "Driver" header as a str.

        Returns None if there is no valid Driver header.
        """
        result = self.headers.get("Driver")
        if not isinstance(result, str):
            return None
        return result

    @hdr_driver.setter
    def hdr_driver(self, value: Optional[str]) -> None:
        """Set the "Driver" header to a str.

        If value is None, the header is removed.
        """
        assert value is None or isinstance(value, str)
        self.set_header("Driver", value)

    def __setitem__(self, key: str, value: NullableHeaderValue) -> None:
        self.set_header(key, value)

    def __getitem__(self, key: str) -> HeaderValue:
        return self.headers[key]

    def __delitem__(self, key: str) -> None:
        self.del_header(key)

    def __iter__(self):
        return iter(self._headers)

    def _update_no_rebuild(
            self,
            other: Union[Mapping[str, NullableHeaderValue], Iterable[Tuple[str, NullableHeaderValue]]]=(),
            /,
            **kwargs: NullableHeaderValue
          ) -> None:
        if isinstance(other, Mapping):
            for key in other:
                self._set_header_no_rebuild(key, other[key])
        elif hasattr(other, "keys"):
            for key in other.keys():  # type: ignore[attr-defined]
                self._set_header_no_rebuild(key, other[key]) # type: ignore[index]
        else:
            for key, value in other:
                self._set_header_no_rebuild(key, value)
        for key, value in kwargs.items():
            self._set_header_no_rebuild(key, value)

    def update(   # type: ignore[override]
            self,
            other: Union[Mapping[str, NullableHeaderValue], Iterable[Tuple[str, NullableHeaderValue]]]=(),
            /,
            **kwargs: NullableHeaderValue
          ) -> None:
        self._update_no_rebuild(other, **kwargs)
        self._rebuild_raw_data()

    def clear(self):
        self.clear_headers()

    def __len__(self):
        return len(self.headers)

    def lower_items(self):
        """Like items(), but with all lowercase keys."""
        return self.headers.lower_items()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SddpDatagram):
            return False
        # we could just compare raw data, but that would distinguish based on sort order of headers
        return (self._statement_line == other._statement_line and
                self._raw_headers == other._raw_headers and
                self._body == other._body)

    # Copy is required
    def copy(self):
        return SddpDatagram(copy_from=self)

    def _rebuild_headers(self) -> None:
        """Rebuild the decoded headers from the raw headers."""
        self._headers.clear()
        for k, v in self._raw_headers.items():
            self._update_header_from_raw_header(k, v)

    def _update_raw_headers_no_rebuild(
            self,
            other: Union[Mapping[str, Optional[str]], Iterable[Tuple[str, Optional[str]]]]=(),
            /,
            **kwargs: Optional[str]
          ) -> None:
        if isinstance(other, Mapping):
            for key in other:
                self._set_raw_header_no_rebuild(key, other[key])
        elif hasattr(other, "keys"):
            for key in other.keys(): # type: ignore[attr-defined]
                self._set_raw_header_no_rebuild(key, other[key]) # type: ignore[index]
        else:
            for key, value in other:
                self._set_raw_header_no_rebuild(key, value)
        for key, value in kwargs.items():
            self._set_raw_header_no_rebuild(key, value)

    def _clear_decoded_headers_no_rebuild(self) -> None:
        for k in self._headers.keys():
            self._raw_headers.pop(k, None)
        self._headers.clear()

    def _rebuild_raw_data(self) -> None:
        """Rebuild the raw data from the statement line, raw headers, and body."""
        raw_data = self.statement_line.encode('utf-8')
        if len(raw_data) != 0:
            raw_data += b'\r\n'
        # Sort the headers by name so that raw data is deterministic
        for k in sorted(self.raw_headers.keys()):
            v = self.raw_headers[k]
            raw_data += encode_http_header(k, v)
        if len(self.body) != 0:
          raw_data += b"\r\n"
          raw_data += self.body
        self._raw_data = raw_data

    def _set_raw_header_no_rebuild(self, name: str, value: Optional[str]) -> None:
        if value is None:
            self._del_header_no_rebuild(name)
        else:
            assert isinstance(value, str)
            self._raw_headers[name] = value
            self._update_header_from_raw_header(name, value)

    def _update_header_from_raw_header(self, name: str, value: str) -> None:
        """Update a decoded header from the raw header value."""
        try:
            self._headers[name] = json.loads(value)
        except json.JSONDecodeError:
            self._headers.pop(name, None)

    def _set_header_no_rebuild(self, name: str, value: NullableHeaderValue) -> None:
        if value is None:
            self._del_header_no_rebuild(name)
        else:
            assert isinstance(value, (str, int, float))
            self.headers[name] = value
            self.raw_headers[name] = json.dumps(value)

    def _del_header_no_rebuild(self, name: str) -> None:
        self.headers.pop(name, None)
        self.raw_headers.pop(name, None)
