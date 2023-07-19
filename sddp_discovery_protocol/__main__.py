#!/usr/bin/env python3

from __future__ import annotations

import sys
import argparse

from jvc_projector.proj import *

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

async def amain(argv: Optional[Sequence[str]]=None) -> int:
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

    args = parser.parse_args(args=argv)

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

    return 0

def main(argv: Optional[Sequence[str]]=None) -> int:
    loop = asyncio.new_event_loop()
    try:
      asyncio.set_event_loop(loop)
      rc = loop.run_until_complete(amain())
    finally:
      loop.close()
    return rc

def run(argv: Optional[Sequence[str]]=None) -> int:
  rc = main(argv)
  return rc

# allow running with "python3 -m", or as a standalone script
if __name__ == "__main__":
  sys.exit(run())
