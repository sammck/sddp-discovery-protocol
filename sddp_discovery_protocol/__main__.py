#!/usr/bin/env python3

# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

from __future__ import annotations

import sys
import argparse
import json
import base64
import asyncio
import logging
from signal import SIGINT, SIGTERM

from sddp_discovery_protocol.internal_types import *

from sddp_discovery_protocol import (
    __version__ as pkg_version,
    SddpServer,
    SddpClient,
    SddpSearchRequest,
    SddpDatagramSubscriber,
    SddpDatagram,
    SddpSocketBinding,
    CaseInsensitiveDict,
    SddpAdvertisementInfo,
    DEFAULT_RESPONSE_WAIT_TIME,
  )
class CmdExitError(RuntimeError):
    exit_code: int

    def __init__(self, exit_code: int, msg: Optional[str]=None):
        if msg is None:
            msg = f"Command exited with return code {exit_code}"
        super().__init__(msg)
        self.exit_code = exit_code

class ArgparseExitError(CmdExitError):
    pass

class NoExitArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        raise ArgparseExitError(status, message)

integer_sddp_headers: List[str] = [ "Max-Age" ]

class CommandHandler:
    _argv: Optional[Sequence[str]]
    _parser: argparse.ArgumentParser
    _args: argparse.Namespace
    _provide_traceback: bool = True

    def __init__(self, argv: Optional[Sequence[str]]=None):
        self._argv = argv

    async def cmd_bare(self) -> int:
        print("A command is required", file=sys.stderr)
        return 1

    def _parse_arg_headers(self, arg_headers: List[str]) -> CaseInsensitiveDict:
        headers: CaseInsensitiveDict[Union[str, int]] = CaseInsensitiveDict()
        for header_assignment in arg_headers:
            value: Union[str, int]
            name, value = header_assignment.split('=', 1)
            if name.lower() in [x.lower() for x in integer_sddp_headers]:
                value = int(value)
            headers[name] = value
        return headers


    async def cmd_server(self) -> int:
        async def notify_handler(info: SddpAdvertisementInfo) -> None:
            results: List[JsonableDict] = []
            datagram = info.datagram
            header_dict: Dict[str, Union[str, int, float]] = dict(datagram.headers)
            summary: JsonableDict = {
                "sddp_version": info.sddp_version,
                "src_addr": f"{info.src_addr[0]}:{info.src_addr[1]}",
                "local_addr": f"{info.socket_binding.unicast_addr[0]}:{info.socket_binding.unicast_addr[1]}",
                "headers": header_dict,
                "monotonic_time": info.monotonic_time,
                "utc_time": info.utc_time.isoformat(),
            }
            if datagram.body is not None and len(datagram.body) > 0:
                summary["body"] = base64.b64encode(datagram.body).decode('ascii')

            print(json.dumps(summary, indent=2, sort_keys=True))

        advertise_interval: float = self._args.advertise_interval
        headers = self._parse_arg_headers(self._args.headers)
        bind_addresses: Optional[List[str]] = self._args.bind_addresses
        if not bind_addresses is None and len(bind_addresses) == 0:
            bind_addresses = None
        server = SddpServer(advertise_interval=advertise_interval, device_headers=headers, bind_addresses=bind_addresses)
        server.add_notify_handler(notify_handler)
        if not self._provide_traceback:
            async def sigint_cleanup() -> None:
                try:
                    await asyncio.shield(server.final_result)
                    logging.debug("sigint_cleanup: Server exited without SIGINT/SIGTERM; exiting")
                except asyncio.CancelledError:
                    logging.debug("sigint_cleanup: Detected SIGINT/SIGTERM, cancelling server")
                    if server.final_result.done():
                        logging.debug("sigint_cleanup: Server already had final_result set--no effect")
                    server.set_final_exception(CmdExitError(1, "Server terminated with SIGINT or SIGTERM"))
            loop = asyncio.get_running_loop()
            sig_task = asyncio.create_task(sigint_cleanup())
            for signal in (SIGINT, SIGTERM):
                loop.add_signal_handler(signal, sig_task.cancel)
        try:
            async with server as s:
                await s.wait_for_done()
        finally:
            if not self._provide_traceback:
                for signal in (SIGINT, SIGTERM):
                    loop.remove_signal_handler(signal)
                sig_task.cancel()
                try:
                    await sig_task
                except asyncio.CancelledError:
                    pass
        return 0

    async def cmd_search(self) -> int:
        response_wait_time: float = self._args.wait_time
        search_pattern: str = self._args.pattern
        include_error_responses: bool = self._args.include_error_responses
        max_responses: int = self._args.max_responses
        bind_addresses: Optional[List[str]] = self._args.bind_addresses
        if not bind_addresses is None and len(bind_addresses) == 0:
            bind_addresses = None
        filter_headers = self._parse_arg_headers(self._args.filter_headers)
        async with SddpClient(response_wait_time=response_wait_time, bind_addresses=bind_addresses) as client:
            async with SddpSearchRequest(
                    client,
                    search_pattern=search_pattern,
                    response_wait_time=response_wait_time,
                    max_responses=max_responses,
                    include_error_responses=include_error_responses,
                    filter_headers=filter_headers,
                ) as search_request:
                async for info in search_request.iter_responses():
                    datagram = info.datagram
                    header_dict: Dict[str, Union[str, int, float]] = dict(datagram.headers)
                    summary: JsonableDict = {
                        "sddp_version": info.sddp_version,
                        "status_code": info.status_code,
                        "status": info.status,
                        "src_addr": f"{info.src_addr[0]}:{info.src_addr[1]}",
                        "local_addr": f"{info.socket_binding.unicast_addr[0]}:{info.socket_binding.unicast_addr[1]}",
                        "headers": header_dict,
                        "monotonic_time": info.monotonic_time,
                        "utc_time": info.utc_time.isoformat(),
                    }
                    if datagram.body is not None and len(datagram.body) > 0:
                        summary["body"] = base64.b64encode(datagram.body).decode('ascii')
                    print(json.dumps(summary, indent=2, sort_keys=True))
                    sys.stdout.flush()

        return 0

    async def cmd_version(self) -> int:
        print(pkg_version)
        return 0

    async def arun(self) -> int:
        """Run the sddp command-line tool with provided arguments

        Args:
            argv (Optional[Sequence[str]], optional):
                A list of commandline arguments (NOT including the program as argv[0]!),
                or None to use sys.argv[1:]. Defaults to None.

        Returns:
            int: The exit code that would be returned if this were run as a standalone command.
        """
        import argparse

        parser = argparse.ArgumentParser(description="Access a secret key/value database.")


        # ======================= Main command

        self._parser = parser
        parser.add_argument('--traceback', "--tb", action='store_true', default=False,
                            help='Display detailed exception information')
        parser.add_argument('--log-level', dest='log_level', default='warning',
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            help='''The logging level to use. Default: warning''')
        parser.set_defaults(func=self.cmd_bare)

        subparsers = parser.add_subparsers(
                            title='Commands',
                            description='Valid commands',
                            help='Additional help available with "<command-name> -h"')


        # ======================= server

        parser_server = subparsers.add_parser('server', description="Run an SDDP server")
        parser_server.add_argument('--advertise-interval', dest='advertise_interval', default=1200, type=int,
                            help='''The interval at which to send device advertisements, in seconds. Default: 2/3 of Max-Age header, or 1200 seconds (20 minutes)''')
        parser_server.add_argument('-H', '--header', dest="headers", action='append', default=[],
                            help='''A <name>=<value> header to include in the device advertisement. May be repeated.''')
        parser_server.add_argument('-b', '--bind', dest="bind_addresses", action='append', default=[],
                            help='''The local unicast IP address to bind to. May be repeated. Default: all local non-loopback unicast addresses.''')
        parser_server.set_defaults(func=self.cmd_server)

        # ======================= search

        parser_search = subparsers.add_parser('search', description="Search for SDDP devices")
        parser_search.add_argument('--pattern', default="*",
                            help='''The device pattern to search for. Default: "*"''')
        parser_search.add_argument('--wait-time', type=float, default=DEFAULT_RESPONSE_WAIT_TIME,
                            help=f'''The amount of time to wait for responses, in seconds. Default: {DEFAULT_RESPONSE_WAIT_TIME}''')
        parser_search.add_argument('-b', '--bind', dest="bind_addresses", action='append', default=[],
                            help='''The local unicast IP address to bind to. May be repeated. Default: all local non-loopback unicast addresses.''')
        parser_search.add_argument('--include-error-responses', dest="include_error_responses", action='store_true', default=False,
                            help='Include error responses in the output. Default: False')
        parser_search.add_argument('--max-responses', type=int, default=0,
                            help='The maximum number of responses to return. Default: 0 (no limit)')
        parser_search.add_argument('-F', '--filter', dest="filter_headers", action='append', default=[],
                            help='''A <name>=<value> header that must match a response for the response to be included. May be repeated.''')
        parser_search.set_defaults(func=self.cmd_search)

        # ======================= version

        parser_version = subparsers.add_parser('version',
                                description='''Display version information.''')
        parser_version.set_defaults(func=self.cmd_version)

        # =========================================================

        try:
            args = parser.parse_args(self._argv)
        except ArgparseExitError as ex:
            return ex.exit_code
        traceback: bool = args.traceback
        self._provide_traceback = traceback

        try:
            logging.basicConfig(
                level=logging.getLevelName(args.log_level.upper()),
            )
            self._args = args
            func: Callable[[], Awaitable[int]] = args.func
            logging.debug(f"Running command {func.__name__}, tb = {traceback}")
            rc = await func()
            logging.debug(f"Command {func.__name__} returned {rc}")
        except Exception as ex:
            if isinstance(ex, CmdExitError):
                rc = ex.exit_code
            else:
                rc = 1
            if rc != 0:
                if traceback:
                    raise
            print(f"sddp: error: {ex}", file=sys.stderr)
        except BaseException as ex:
            print(f"sddp: Unhandled exception: {ex}", file=sys.stderr)
            raise

        return rc

    def run(self) -> int:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            rc = loop.run_until_complete(self.arun())
        finally:
            loop.close()
        return rc

def run(argv: Optional[Sequence[str]]=None) -> int:
    try:
        rc = CommandHandler(argv).run()
    except CmdExitError as ex:
        rc = ex.exit_code
    return rc

async def arun(argv: Optional[Sequence[str]]=None) -> int:
    try:
        rc = await CommandHandler(argv).arun()
    except CmdExitError as ex:
        rc = ex.exit_code
    return rc

# allow running with "python3 -m", or as a standalone script
if __name__ == "__main__":
    sys.exit(run())

