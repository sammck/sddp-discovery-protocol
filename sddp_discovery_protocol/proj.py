#!/usr/bin/env python3

from __future__ import annotations

from .internal_types import *


import argparse
import logging
import socket
import socketserver
import time
import asyncio
import os
from enum import Enum

from types import TracebackType

from .constants import (
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    STABLE_POWER_TIMEOUT,
    PJ_OK,
    PJREQ,
    PJACK,
    PACKET_MAGIC,
    END_OF_PACKET,
    MAX_PACKET_LENGTH,
    MIN_PACKET_LENGTH,
  )

class PacketType(Enum):
    """The first byte of a packet sent to or received from the projector, identifying its type."""
    UNKNOWN = -1
    BASIC_COMMAND = 0x21
    ADVANCED_COMMAND = 0x3f
    BASIC_RESPONSE = 0x06
    ADVANCED_RESPONSE = 0x40


class JvcProjectorException(Exception):
    """An exception raised by the JVC projector client package"""
    pass

class Packet:
    """
    All packets sent to or received from the projector are of the raw form:
        <packet_type_byte> 89 01 <two_byte_command_code> <packet_payload> 0A

    The 0A byte is a newline character, and is the terminating byte for all packets. It is
    never present in any of the other portions of a packet.

    The two-byte command code in responses is the same as the command code in the
    corresponding command packet.
    """

    raw_data: bytes
    """The raw packet data, including the terminating newline character"""

    def __init__(self, raw_data: bytes):
        self.raw_data = raw_data

    def __str__(self) -> str:
        return f"Packet({self.raw_data.hex(' ')})"

    def __repr__(self) -> str:
        return str(self)

    @property
    def packet_type_byte(self) -> int:
        """The first byte of the packet, which identifies the type of packet"""
        return self.raw_data[0]

    @property
    def packet_type(self) -> PacketType:
        """The type of packet. Returns PacketType.UNKNOWN if the packet type is not recognized."""
        try:
            result = PacketType(self.packet_type_byte)
        except ValueError:
            result = PacketType.UNKNOWN
        return result

    @property
    def packet_magic(self) -> bytes:
        """The packet magic validation bytes, which are the first two bytes after the packet type"""
        return self.raw_data[1:3]

    @property
    def command_code(self) -> bytes:
        """The 2-byte command code of the packet, which are the first two bytes after the packet magic"""
        return self.raw_data[3:5]

    @property
    def packet_payload(self) -> bytes:
        """The payload of the packet, excluding the packet type, the magic bytes, the
           command code, and the terminating newline character."""
        return self.raw_data[5:-1]

    @property
    def packet_final_byte(self) -> int:
        """The terminating byte of the packet. Should always be 0x0a."""
        return self.raw_data[-1]

    @property
    def is_valid(self) -> bool:
        """Returns True iff the packet is a well-formed packet at the simplest level"""
        if not (MIN_PACKET_LENGTH <= len(self.raw_data) <= MAX_PACKET_LENGTH):
            return False
        if self.packet_magic != PACKET_MAGIC:
            return False
        if not self.packet_final_byte == END_OF_PACKET:
            return False
        if self.packet_type == PacketType.UNKNOWN:
            return False
        return True

    def validate(self) -> None:
        if len(self.raw_data) < MIN_PACKET_LENGTH:
            raise JvcProjectorException(f"Packet too short: {self}")
        if len(self.raw_data) > MAX_PACKET_LENGTH:
            raise JvcProjectorException(f"Packet too long: {self}")
        if self.packet_magic != PACKET_MAGIC:
            raise JvcProjectorException(f"Packet magic validator byte mismatch: {self}")
        if not self.packet_final_byte == END_OF_PACKET:
            raise JvcProjectorException(f"Packet does not end in newline: {self}")
        if self.packet_type == PacketType.UNKNOWN:
            raise JvcProjectorException(f"Unrecognized packet type byte {self.packet_type_byte:02x}: {self}")

    @property
    def is_basic_command(self) -> bool:
        """Returns True iff the packet is a well-formed basic command packet"""
        return self.is_valid and self.packet_type == PacketType.BASIC_COMMAND

    @property
    def is_advanced_command(self) -> bool:
        """Returns True iff the packet is a well-formed advanced command packet"""
        return self.is_valid and self.packet_type == PacketType.ADVANCED_COMMAND

    @property
    def is_command(self) -> bool:
        """Returns True iff the packet is a well-formed command packet"""
        return self.is_valid and self.packet_type in (PacketType.BASIC_COMMAND, PacketType.ADVANCED_COMMAND)

    @property
    def is_basic_response(self) -> bool:
        """Returns True iff the packet is a well-formed basic response packet"""
        return self.is_valid and self.packet_type == PacketType.BASIC_RESPONSE

    @property
    def is_advanced_response(self) -> bool:
        """Returns True iff the packet is a well-formed advanced response packet"""
        return self.is_valid and self.packet_type == PacketType.ADVANCED_RESPONSE

    @property
    def is_response(self) -> bool:
        """Returns True iff the packet is a well-formed response packet"""
        return self.is_valid and self.packet_type in (PacketType.BASIC_RESPONSE, PacketType.ADVANCED_RESPONSE)

    @classmethod
    def create(cls, packet_type: PacketType, command_code: bytes, payload: Optional[bytes]=None) -> Packet:
        if packet_type == PacketType.UNKNOWN:
            raise JvcProjectorException(f"Cannot create packet of UNKNOWN type")
        if len(command_code) != 2:
            raise JvcProjectorException(f"Command code not 2 bytes: {command_code.hex(' ')}")
        if payload is None:
            payload = b''
        raw_data = bytes([packet_type.value]) + PACKET_MAGIC + command_code + payload + bytes([END_OF_PACKET])
        return cls(raw_data)

    @classmethod
    def create_basic_command(cls, cmd_bytes: bytes, payload: Optional[bytes]=None) -> Packet:
        """Creates a basic command packet"""
        return cls.create(PacketType.BASIC_COMMAND, cmd_bytes, payload)

    @classmethod
    def create_advanced_command(cls, cmd_bytes: bytes, payload: Optional[bytes]=None) -> Packet:
        """Creates a basic command packet"""
        return cls.create(PacketType.ADVANCED_COMMAND, cmd_bytes, payload)

    @classmethod
    def create_command(cls, cmd_bytes: bytes, payload: Optional[bytes]=None, is_advanced: bool=False) -> Packet:
        """Creates a basic or advanced command packet"""
        if is_advanced:
            result = cls.create_advanced_command(cmd_bytes, payload)
        else:
            result = cls.create_basic_command(cmd_bytes, payload)
        return result

class JvcResponse:
    """A response to a JVC command

    Raw command responses are either basic or advanced.

    For a command packet with a raw form
        21 89 01 <cmd_byte_0> <cmd_byte_1> <optional_cmd_payload> 0A

    Basic command response packets are of the form:

        06 89 01 <cmd_byte_0> <cmd_byte_1> 0A

    Advanced command responses consist of a basic command response packet followed
    by a response return code packet of the form:

        40 89 01 <cmd_byte_0> <cmd_byte_1> <return_code_payload> 0A

    """
    command: JvcCommand
    basic_response_packet: Packet
    advanced_response_packet: Optional[Packet]

    def __init__(self, command: JvcCommand, basic_response_packet: Packet, advanced_response_packet: Optional[Packet]=None):
        if not basic_response_packet.is_basic_response:
            raise JvcProjectorException(f"Basic response packet expected: {basic_response_packet}")
        if basic_response_packet.command_code != command.command_code:
            raise JvcProjectorException(f"Basic response packet command code {basic_response_packet.command_code.hex(' ')} does not match command {command}: {basic_response_packet}")
        if len(basic_response_packet.packet_payload) != 0:
            raise JvcProjectorException(f"Basic response packet payload expected to be empty, but got: {basic_response_packet}")
        if command.is_advanced:
            if advanced_response_packet is None:
                raise JvcProjectorException(f"Advanced command {command} requires advanced response packet, but got: {advanced_response_packet}")
            if not advanced_response_packet.is_advanced_response:
                raise JvcProjectorException(f"Advanced response packet expected, but got: {advanced_response_packet}")
            if advanced_response_packet.command_code != command.command_code:
                raise JvcProjectorException(f"Advanced response packet command code {advanced_response_packet.command_code.hex(' ')} does not match command {command}: {advanced_response_packet}")
            if not command.expected_payload_length is None:
                if len(advanced_response_packet.packet_payload) != command.expected_payload_length:
                    raise JvcProjectorException(f"Advanced response packet payload length {len(advanced_response_packet.packet_payload)} does not match command {command} expected length {command.expected_payload_length}: {advanced_response_packet}")
        else:
            if not advanced_response_packet is None:
                raise JvcProjectorException(f"Basic command {command} does not expect an advanced response packet")
        self.command = command
        self.basic_response_packet = basic_response_packet
        self.advanced_response_packet = advanced_response_packet
        self.post_init()

    def post_init(self) -> None:
        """Post-initialization hook, allows subclasses to perform additional initialization"""
        pass

    @property
    def name(self) -> str:
        return self.command.name

    @property
    def raw_data(self) -> bytes:
        """Returns the raw data of the response. If the response is an advanced response,
           the payload of the advanced response packet is appended to the payload of the
           basic response packet"""
        data = self.basic_response_packet.raw_data
        if not self.advanced_response_packet is None:
            data = data[:] + self.advanced_response_packet.raw_data
        return data

    def __str__(self) -> str:
        return f"JvcResponse({self.name}: [{self.raw_data.hex(' ')}])"

    @property
    def is_advanced(self) -> bool:
        """Returns True iff the response is an advanced response"""
        return not self.advanced_response_packet is None

    @property
    def payload(self) -> bytes:
        """Returns the payload of the advanced response packet, if any"""
        return b'' if self.advanced_response_packet is None else self.advanced_response_packet.packet_payload

    def __repr__(self) -> str:
        return str(self)

class JvcCommand:
    """A command to a JVC projector"""
    name: str
    command_packet: Packet
    response_cls: type[JvcResponse]
    expected_payload_length: Optional[int]

    def __init__(
            self,
            name: str,
            command_packet: Packet,
            response_cls: type[JvcResponse]=JvcResponse,
            expected_payload_length: Optional[int]=None
          ):
        command_packet.validate()
        if not command_packet.packet_type in (PacketType.BASIC_COMMAND, PacketType.ADVANCED_COMMAND):
            raise JvcProjectorException(f"Cannot create JvcCommand from non-command packet: {command_packet}")
        self.name = name
        self.command_packet = command_packet
        self.response_cls = response_cls
        self.expected_payload_length = expected_payload_length

    @property
    def command_code(self) -> bytes:
        """Returns the command code of the command"""
        return self.command_packet.command_code

    @property
    def payload_data(self) -> bytes:
        """Returns the payload of the command"""
        return self.command_packet.packet_payload

    @property
    def packet_type(self) -> PacketType:
        """Returns the packet type of the command"""
        return self.command_packet.packet_type

    @property
    def is_advanced(self) -> bool:
        """Returns True iff the command is an advanced command"""
        return self.command_packet.is_advanced_command

    @classmethod
    def create(
            cls,
            name: str,
            cmd_bytes: bytes,
            payload: Optional[bytes]=None,
            is_advanced: bool=False,
            response_cls: type[JvcResponse]=JvcResponse,
            expected_payload_length: Optional[int]=None
          ) -> JvcCommand:
        """Creates a basic or advanced JvcCommand"""
        packet_type = PacketType.ADVANCED_COMMAND if is_advanced else PacketType.BASIC_COMMAND
        command_packet = Packet.create(packet_type, cmd_bytes, payload)
        return cls(name, command_packet, response_cls=response_cls, expected_payload_length=expected_payload_length)

    @classmethod
    def create_basic(
            cls,
            name: str,
            cmd_bytes: bytes,
            payload: Optional[bytes]=None,
            response_cls: type[JvcResponse]=JvcResponse,
          ) -> JvcCommand:
        return cls.create(
                name,
                cmd_bytes,
                payload=payload,
                is_advanced=False,
                response_cls=response_cls
              )

    @classmethod
    def create_advanced(
            cls,
            name: str,
            cmd_bytes: bytes,
            payload: Optional[bytes]=None,
            response_cls: type[JvcResponse]=JvcResponse,
            expected_payload_length: Optional[int]=None
          ) -> JvcCommand:
        return cls.create(
                name,
                cmd_bytes,
                payload=payload,
                is_advanced=True,
                response_cls=response_cls,
                expected_payload_length=expected_payload_length
              )

    async def __call__(self, session: JvcProjectorSession) -> JvcResponse:
        logging.debug(f"Sending command {self}")
        basic_response_packet, advanced_response_packet = await session.transact(self.command_packet)
        response = self.create_response(basic_response_packet, advanced_response_packet=advanced_response_packet)
        logging.debug(f"Received response {response}")
        return response

    def create_response(self, basic_response_packet: Packet, advanced_response_packet: Optional[Packet]=None) -> JvcResponse:
        response =  self.response_cls(self, basic_response_packet, advanced_response_packet=advanced_response_packet)
        return response

    def __str__(self) -> str:
        return f"JvcCommand({self.name}: {self.command_packet})"

    def __repr__(self) -> str:
        return str(self)

class BasicCommand(JvcCommand):
    """A JVC command that returns a basic response"""

    def __init__(self, name: str, command_code: bytes, payload: Optional[bytes]=None, response_cls: type[JvcResponse]=JvcResponse):
        command_packet = Packet.create(PacketType.BASIC_COMMAND, command_code, payload)
        super().__init__(name, command_packet, response_cls=response_cls)

class AdvancedCommand(JvcCommand):
    """A JVC command that returns a basic response"""

    def __init__(
            self,
            name: str,
            command_code: bytes,
            payload: Optional[bytes]=None,
            response_cls: type[JvcResponse]=JvcResponse,
            expected_payload_length: Optional[int]=None
          ):
        command_packet = Packet.create(PacketType.ADVANCED_COMMAND, command_code, payload)
        super().__init__(name, command_packet, response_cls=response_cls, expected_payload_length=expected_payload_length)

null_command = BasicCommand("Null Command", b'\x00\x00')
'''A test command that has no effect but returns a basic response'''

class PowerStatus(Enum):
    UNKNOWN = -1
    STANDBY = 0x30
    ON = 0x31
    COOLING = 0x32
    WARMING = 0x33
    EMERGENCY = 0x34

class OneByteReturnCodeResponse(JvcResponse):
    """A response that contains a single byte return code"""

    def post_init(self) -> None:
        if len(self.payload) != 1:
            raise JvcProjectorException(f"{self}: expected 1-byte payload, got {len(self.payload)}")

    @property
    def return_code(self) -> int:
        return self.payload[0]

class PowerStatusResponse(OneByteReturnCodeResponse):
    power_status: Optional[PowerStatus] = None

    def post_init(self) -> None:
        super().post_init()
        if self.return_code in [status.value for status in PowerStatus]:
            self.power_status = PowerStatus(self.return_code)
        else:
            self.power_status = PowerStatus.UNKNOWN
            logging.warning(f"{self}: Unexpected power status return code 0x{self.return_code:02x}; represented as PowerStatus.UNKNOWN")

    @property
    def power_status_code(self) -> int:
        return self.return_code

    def __str__(self) -> str:
        return f"PowerStatusResponse({self.command.name}: {self.power_status.name} [{self.raw_data.hex(' ')}])"

    @property
    def power_is_on(self) -> bool:
        return self.power_status == PowerStatus.ON


class PowerStatusCommand(AdvancedCommand):
    def __init__(self):
        super().__init__("Power Status", b'\x50\x57', response_cls=PowerStatusResponse, expected_payload_length=1)

power_status_command = PowerStatusCommand()
"""A command that returns the power status of the projector"""

class ModelStatusResponse(JvcResponse):
    model_map: dict[str, str] = {
        "ILAFPJ -- B5A2": "DLA-NZ8",
        "ILAFPJ -- -XH4": "DLA-HD350",
        "ILAFPJ -- -XH7": "DLA-RS10",
        "ILAFPJ -- -XH5": "DLA-HD750,DLA-RS20",
        "ILAFPJ -- -XH8": "DLA-HD550",
        "ILAFPJ -- -XHA": "DLA-RS15",
        "ILAFPJ -- -XH9": "DLA-HD950,DLA-HD990,DLA-RS25,DLA-RS35",
        "ILAFPJ -- -XHB": "DLA-X3,DLA-RS40",
        "ILAFPJ -- -XHC": "DLA-X7,DLA-X9,DLA-RS50,DLA-RS60",
        "ILAFPJ -- -XHE": "DLA-X30,DLA-RS45",
        "ILAFPJ -- -XHF": "DLA-X70R,DLA-X90R,DLA-RS55,DLA-RS65",
    }
    model_id: str = "UNKNOWN"

    def post_init(self) -> None:
        if len(self.payload) != 14:
            raise JvcProjectorException(f"{self}: expected 14-byte payload, got {len(self.payload)}")
        self.model_id = self.payload.decode('utf-8')

    @property
    def model_name(self) -> str:
        return self.model_map.get(self.model_id, f"UNKNOWN (id: {self.model_id})")

    def __str__(self) -> str:
        return f"ModelStatusResponse({self.command.name}: '{self.model_id}' [{self.raw_data.hex(' ')}])"


class ModelStatusCommand(AdvancedCommand):
    def __init__(self):
        super().__init__("Model Status", b'\x4D\x44', response_cls=ModelStatusResponse, expected_payload_length=14)

model_status_command = ModelStatusCommand()
"""A command that returns the projector's model ID"""

power_on_command = BasicCommand("Power On", b'\x50\x57', payload=b'\x31')
"""A command that turns the projector on. Note: At least on DLA-NZ8, this command does not return a response
   if the projector is not STANDBY, resulting in a timeout exception."""

power_off_command = BasicCommand("Power Off", b'\x50\x57', payload=b'\x30')
"""A command that turns the projector into standby mode. Note: At least on DLA-NZ8, this command does not return a response
   if the projector is not ON, resulting in a timeout exception."""

class JvcProjectorSession:
    projector: JvcProjector
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None

    def __init__(self, projector: JvcProjector):
        self.projector = projector

    async def _async_dispose(self) -> None:
        try:
            if self.reader is not None:
                self.reader.feed_eof()
        except Exception as e:
            logging.exception("Exception while closing reader")
        try:
            if self.writer is not None:
                self.writer.close()
                await self.writer.wait_closed()
        except Exception as e:
            logging.exception("Exception while closing writer")

    async def __aenter__(self) -> JvcProjectorSession:
        logging.debug("Entering async context manager")
        return self

    # exit the async context manager
    async def __aexit__(
            self,
            exc_type: type[BaseException],
            exc_val: Optional[BaseException],
            exc_tb: TracebackType
          ) -> Optional[bool]:
        if exc_val is None:
            logging.debug("Exiting async context manager")
        else:
            logging.exception(f"Exiting async context manager with exception, exc_type={exc_type}, exc_val={exc_val}, exc_tb={exc_tb}")

        await self._async_dispose()

        return False

    @property
    def host(self) -> str:
        return self.projector.host

    @property
    def port(self) -> int:
        return self.projector.port

    @property
    def timeout_secs(self) -> Optional[float]:
        return self.projector.timeout_secs

    @property
    def password(self) -> Optional[str]:
        return self.projector.password

    @classmethod
    async def create(cls, projector: JvcProjector):
        self = cls(projector)
        try:
            await self.connect()
        except BaseException as e:
            logging.exception("Exception while connecting")
            await self._async_dispose()
            raise e
        return self

    async def read_response_packet(self) -> Packet:
        """Reads a single response packet from the projector, with timeout"""
        assert self.reader is not None

        packet_bytes = await asyncio.wait_for(self.reader.readline(), self.timeout_secs)
        logging.debug(f"Read packet bytes: {packet_bytes.hex(' ')}")
        if len(packet_bytes) == 0:
            raise JvcProjectorException("Connection closed by projector")
        if packet_bytes[-1] != 0x0a:
            raise JvcProjectorException(f"Connection closed by projector with partial packet: {packet_bytes.hex(' ')}")
        try:
            result = Packet(packet_bytes)
            result.validate()
        except Exception as e:
            raise JvcProjectorException(f"Invalid response packet received from projector: {packet_bytes.hex(' ')}") from e
        if not result.is_response:
            raise JvcProjectorException(f"Received packet is not a response: {result}")
        return result

    async def read_response_packets(self, command_code: bytes, is_advanced: bool=False) -> Tuple[Packet, Optional[Packet]]:
        """Reads a basic response packet and an optional advanced response packet"""
        basic_response_packet = await self.read_response_packet()
        advanced_response_packet: Optional[Packet] = None
        if basic_response_packet.command_code != command_code:
            raise JvcProjectorException(f"Received response packet for wrong command code (expected {command_code.hex(' ')}): {basic_response_packet}")
        if basic_response_packet.is_advanced_response:
            raise JvcProjectorException(f"Received advanced response packet before basic response packet: {basic_response_packet}")
        if is_advanced:
            advanced_response_packet = await self.read_response_packet()
            if advanced_response_packet.command_code != command_code:
                raise JvcProjectorException(f"Received second response packet for wrong command code (expected {command_code.hex(' ')}): {advanced_response_packet}")
            if not advanced_response_packet.is_advanced_response:
                raise JvcProjectorException(f"Received second basic response packet instead of advanced response packet: {advanced_response_packet}")
        return (basic_response_packet, advanced_response_packet)

    async def read_exactly(self, length: int) -> bytes:
        assert self.reader is not None

        data = await asyncio.wait_for(self.reader.readexactly(length), self.timeout_secs)
        logging.debug(f"Read exactly {len(data)} bytes: {data.hex(' ')}")
        return data

    async def write_exactly(self, data: bytes | bytearray | memoryview) -> None:
        assert self.writer is not None

        logging.debug(f"Writing exactly {len(data)} bytes: {data.hex(' ')}")
        self.writer.write(data)
        await asyncio.wait_for(self.writer.drain(), self.timeout_secs)

    async def send_packet(self, packet: Packet) -> None:
        """Sends a packet to the projector"""
        await self.write_exactly(packet.raw_data)

    async def transact(
            self,
            command_packet: Packet,
          ) -> Tuple[Packet, Optional[Packet]]:
        """Sends a command packet and reads the response packets"""
        await self.send_packet(command_packet)
        basic_response_packet, advanced_response_packet = await self.read_response_packets(
            command_packet.command_code, command_packet.is_advanced_command)
        return (basic_response_packet, advanced_response_packet)

    async def command(self, cmd: JvcCommand) -> JvcResponse:
        result = await cmd(self)
        return result

    async def cmd_null(self) -> None:
        await self.command(null_command)

    async def cmd_power_status(self) -> PowerStatus:
        response = await self.command(power_status_command)
        return response.power_status

    async def cmd_power_on(self) -> None:
        await self.command(power_on_command)

    async def cmd_power_off(self) -> None:
        await self.command(power_off_command)

    async def wait_for_power_stable(self) -> PowerStatus:
        """Waits for the power status to become stable (e.g., not WARMING or COOLING)"""

        async def poll_for_stable_power() -> PowerStatus:
            while True:
                response = await self.cmd_power_status()
                if response in [PowerStatus.ON, PowerStatus.STANDBY]:
                    return response
                await asyncio.sleep(1)

        result = await asyncio.wait_for(poll_for_stable_power(), 70)
        return result

    async def power_on_and_wait(self):
        """Turns the projector on if it is not already on, and waits for power status to be stable (e.g., not WARMING)"""
        status = await self.wait_for_power_stable()
        if status == PowerStatus.STANDBY:
            await self.cmd_power_on()
            status = await self.wait_for_power_stable()
        return status

    async def power_off_and_wait(self):
        """Turns the projector off if it is not already off, and waits for power status to be stable (e.g., not COOLING)"""
        status = await self.wait_for_power_stable()
        if status == PowerStatus.ON:
            await self.cmd_power_off()
            status = await self.wait_for_power_stable()
        return status

    async def cmd_model_status(self) -> ModelStatusResponse:
        response = await self.command(model_status_command)
        return response

    async def cmd_model_id(self) -> str:
        response = await self.cmd_model_status()
        return response.model_id

    async def cmd_model_name(self) -> str:
        response = await self.cmd_model_status()
        return response.model_name

    async def connect(self) -> None:
        assert self.reader is None and self.writer is None
        logging.debug(f"Connecting to: {self.projector}")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        # Perform the initial handshake. This is a bit weird, since the projector
        # sends a greeting, then we send a request, then the projector sends an
        # acknowledgement, but none of these include a terminating newline.
        logging.debug(f"Handshake: Waiting for greeting")
        greeting = await self.read_exactly(len(PJ_OK))
        if greeting != PJ_OK:
            raise JvcProjectorException(f"Handshake: Unexpected greeting (expected {PJ_OK}): {greeting.hex}")
        logging.debug(f"Handshake: Received greeting: {greeting.hex(' ')}")
        # newer projectors (e.g., DLA-NX8) require a password to be appended to the PJREQ blob
        # (with an underscore separator). Older projectors (e.g., DLA-X790) do not accept a password.
        req_data = PJREQ if self.password is None else PJREQ + b'_' + self.password.encode('utf-8')
        logging.debug(f"Handshake: writing auth data: {req_data.hex(' ')}")
        await self.write_exactly(req_data)
        pjack = await asyncio.wait_for(self.reader.readexactly(len(PJACK)), self.timeout_secs)
        logging.debug(f"Handshake: Read exactly {len(pjack)} bytes: {pjack.hex(' ')}")
        if pjack != PJACK:
            raise JvcProjectorException(f"Handshake: Unexpected ack (expected {PJACK.hex(' ')}): {pjack.hex(' ')}")
        logging.info(f"Handshake: {self} connected and authenticated")

    def __str__(self) -> str:
        return f"JvcProjectorSession(host={self.host}, port={self.port})"

    def __repr__(self) -> str:
       return str(self)

    async def close(self) -> None:
       await self._async_dispose()


class JvcProjector:
    host: str
    port: int
    password: Optional[str]
    timeout_secs: float

    def __init__(
            self,
            host: str,
            port: int = DEFAULT_PORT,
            password: Optional[str] = None,
            timeout_secs: float = DEFAULT_TIMEOUT
          ):
        self.host = host
        self.port = port
        self.password = password
        self.timeout_secs = timeout_secs

    async def connect(self) -> JvcProjectorSession:
        return await JvcProjectorSession.create(self)

    def __str__(self):
        return f"JvcProjector(host={self.host}, port={self.port}, password={self.password}, timeout_secs={self.timeout_secs})"

    def __repr__(self):
        return str(self)

async def run_command(session: JvcProjectorSession, argv: List[str]) -> None:
    if len(argv) < 1:
        raise ValueError("Missing command")
    if len(argv) > 1:
        raise ValueError("Too many arguments")
    cmdname = argv[0]
    if cmdname == "on":
        await session.power_on_and_wait()
    elif cmdname == "off":
        await session.power_off_and_wait()
    elif cmdname == "power_status":
        power_status = await session.cmd_power_status()
        print(f"Power status={power_status}")
    elif cmdname == "model_id":
        model_id = await session.cmd_model_id()
        print(f"Model ID={model_id}")
    elif cmdname == "model_name":
        model_name = await session.cmd_model_name()
        print(f"Model name={model_name}")
    elif cmdname == "null":
        await session.cmd_null()
    else:
        raise ValueError(f"Unknown command: {cmdname}")

async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--port", default=20554, type=int,
        help="JVC projector port number to connect to. Default: 20554")
    parser.add_argument("-t", "--timeout", default=2.0, type=float,
        help="Timeout for network operations (seconds). Default: 2.0")
    parser.add_argument("-l", "--loglevel", default="ERROR",
        help="Logging level. Default: ERROR.",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"])
    parser.add_argument("-p", "--password", default=None,
        help="Password to use when connecting to newer JVC hosts (e.g., DLA-NZ8). Default: use ENV var JVC_PROJECTOR_PASSWORD, or no password.")
    parser.add_argument("-H", "--host", help="JVC projector hostname or IP address. Default: Use env var JVC_PROJECTOR_HOST")
    parser.add_argument('command', nargs='*', default=[])

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.getLevelName(args.loglevel),
        format="%(asctime)s %(levelname)s %(filename)s:%(lineno)d] %(message)s",
        datefmt="%F %H:%M:%S")

    password: Optional[str] = args.password
    if password is None:
        password = os.getenv("JVC_PROJECTOR_PASSWORD")
    if not password is None and password == '':
        password = None

    host: Optional[str] = args.host
    if host is None:
        host = os.getenv("JVC_PROJECTOR_HOST")
        if host is None:
            raise Exception("No projector host specified. Use --host or set env var JVC_PROJECTOR_HOST")

    port: int = args.port
    timeout_secs: float = args.timeout
    cmd_args: List[str] = args.command


    projector = JvcProjector(
        host,
        port=port,
        password=password,
        timeout_secs=timeout_secs)


    async with await projector.connect() as session:
        await session.command(null_command)
        power_status = await session.cmd_power_status()
        print(f"Power status: {power_status}")
        model_name = await session.cmd_model_name()
        print(f"Model name: {model_name}")
        if len(cmd_args) > 0:
            await run_command(session, cmd_args)
            power_status = await session.cmd_power_status()
            print(f"Power status: {power_status}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
