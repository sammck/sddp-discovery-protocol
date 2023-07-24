#!/usr/bin/env python3

import logging
import asyncio
import sddp_discovery_protocol as sddp

#logging.basicConfig(level=logging.DEBUG)

async def amain():
    # all parameters to SddpClient are optional; they allow you to set the IP addresses to bind to, etc.
    async with sddp.SddpClient() as client:
        # Entering the client.search() context manager sends the search multicast request and reliably collects responses.
        # Parameters are optional; they allow you to set search filters, max wait time, max returned responses, etc.
        async with client.search() as search_request:
            # search_request.iter_responses() is an async generator that yields SddpResponseInfo objects
            # as they come in until the max wait time has elapsed or the max number of responses has been received.
            async for response_info in search_request.iter_responses():
                print(response_info.datagram)
                # It is possible to exit the loop early here if you found what you're looking for

loop = asyncio.new_event_loop()
try:
    asyncio.set_event_loop(loop)
    loop.run_until_complete(amain())
finally:
    loop.close()
