#!/usr/bin/env python3

import logging
import asyncio
import sddp_discovery_protocol as sddp

logging.basicConfig(level=logging.DEBUG)

device_headers = {
    "Type": "Acme:TestDevice",
    "Primary-Proxy": "test-device",
    "Proxies": "test-device",
    "Manufacturer": "Acme",
    "Model": "TestDevPlus",
    "Driver": "test-device_Acme_TestDevPlus.c4i",
}

async def amain():
    # The SddpServerContext manager starts the server listening on the multicast port, sending out advertisements,
    # and responding to search requests.  When the context manager exits, the server will be stopped.
    async with sddp.SddpServer(device_headers=device_headers) as server:
        # This will wait forever unless another task stops the server
        await server.wait_for_done()        

loop = asyncio.new_event_loop()
try:
    asyncio.set_event_loop(loop)
    loop.run_until_complete(amain())
finally:
    loop.close()
