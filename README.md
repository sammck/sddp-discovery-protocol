sddp-discovery-protocol: Protocol library for Control4's Simple Device Discovery Protocol (SDDP)
=================================================

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Latest release](https://img.shields.io/github/v/release/sammck/sddp-discovery-protocol.svg?style=flat-square&color=b44e88)](https://github.com/sammck/sddp-discovery-protocol/releases)

A command-line tool and API for servers and clients of Control4's Simple Device Discovery Protocol (SDDP).

Table of contents
-----------------

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
  * [Command line](#command-line)
  * [API](api)
* [Known issues and limitations](#known-issues-and-limitations)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Authors and history](#authors-and-history)


Introduction
------------

Simple Device Discovery Protocol (SDDP) is a simple multicast discovery protocol implemented by many "smart
home" devices to allow a controlling agent to easily discover and connect to devices on a local subnet.

SDDP was created by [Control4](https://www.control4.com/), a provider of whole-home automation systems. While
it is quite similar to UPnP's standard Simple Service Discovery Protocol
([SSDP](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol)--note the similar but different spelling),
and it serves a virtually identical purpose, SDDP is **not** a standard protocol and it is not publicly
documented. The protocol as implemented by this package was inferred through observation of network traffic

#### Servers
Controllable smart devices implement the server side of the SDDP protocol. They listen on a well-known
UDP multicast address 239.255.255.250:1902, and do the following:

* Periodically (typically every 20 minutes) send an SDDP NOTIFY packet to the multicast address
  advertising their presence. An example of such a packet is:

  ```
  NOTIFY ALIVE SDDP/1.0\r\n
  From: "192.168.4.237:1902"\r\n
  Host: "JVC_PROJECTOR-E0DADC152802"\r\n
  Max-Age: 1800\r\n
  Type: "JVCKENWOOD:Projector"\r\n
  Primary-Proxy: "projector"\r\n
  Proxies: "projector"\r\n
  Manufacturer: "JVCKENWOOD"\r\n
  Model: "DLA-RS3100_NZ8"\r\n
  Driver: "projector_JVCKENWOOD_DLA-RS3100_NZ8.c4i"\r\n
  ```
  Note that, as with all SDDP packets, there is a statement line, followed by some header lines, each separated with "\r\n". Formatting of the headers is with the same rules as HTTP headers. All string
  header values are enclosed in double quotes. This package assumes that json.loads() will correctly
  decode all header values.

* Receive SDDP NOTIFY packets sent to the multicast address from other devices. Most devices
  will probably discard these unless they are interested in seeing other devices come and go

* Receive and respond to SDDP SEARCH packets sent to the multicast address by clients that are performing discovery.
  An example of such a search packet is:
  ```
  SEARCH * SDDP/1.0\r\n
  Host: "192.168.4.237:24378"\r\n
  ```
  The device will respond to a valid SEARCH request packet with a SEARCH response packet sent
  from their own unicast address on port 1902 to the unicast address from which the request came.
  The response looks very much like the NOTIFY packet, but the statement line is different; e.g.,:
  ```
  SDDP/1.0 200 OK\r\n
  From: "192.168.4.237:1902"\r\n
  Host: "JVC_PROJECTOR-E0DADC152802"\r\n
  Max-Age: 1800\r\n
  Type: "JVCKENWOOD:Projector"\r\n
  Primary-Proxy: "projector"\r\n
  Proxies: "projector"\r\n
  Manufacturer: "JVCKENWOOD"\r\n
  Model: "DLA-RS3100_NZ8"\r\n
  Driver: "projector_JVCKENWOOD_DLA-RS3100_NZ8.c4i"\r\n
  ```
#### Clients
Apps that wish to discover devices on the local subnet implement the client side of SDDP.
They send from and receive on an arbitrary dynamic UDP port on their unicast address.

To perform discovery, an SDDP client sends an SDDP SEARCH packet from its unicast address
and port to to the SDDP multicast address 239.255.255.250:1902; e.g.:
```
SEARCH * SDDP/1.0\r\n
Host: "192.168.4.237:24378"\r\n
```
where the 'Host' header is set to the client's unicast address and port.

Each SDDP server device on the network will immediately respond to the SEARCH packet
with a SEARCH response packet sent directly to the client's unicast address and port; e.g.,:
```
SDDP/1.0 200 OK\r\n
From: "192.168.4.237:1902"\r\n
Host: "JVC_PROJECTOR-E0DADC152802"\r\n
Max-Age: 1800\r\n
Type: "JVCKENWOOD:Projector"\r\n
Primary-Proxy: "projector"\r\n
Proxies: "projector"\r\n
Manufacturer: "JVCKENWOOD"\r\n
Model: "DLA-RS3100_NZ8"\r\n
Driver: "projector_JVCKENWOOD_DLA-RS3100_NZ8.c4i"\r\n
```

The client will then collect the responses from all server devices and use them
for discovery.

The client waits for an arbitrary period of time (by default, in this package, 3 seconds)
before assuming that all devices have responded.

Package
-------
Python package `sddp-discovery-protocol` provides a command-line tool as well as a runtime API for implementing the client and server sides of SDDP.

Some key features of sddp-discovery-protocol:

* Cross-platform (Linux, MacOS, Windows)
* Fully async model with coroutine pattern (no synchronous callbacks).
* Both client and server supports multi-homed operation (multiple network adapters)
* Server customizes 'From' header for each
* Server supports periodic multicast NOTIFY advertisement and responds to SEARCH queries
* Server supports collection of NOTIFY advertisements from other SDDP servers on the subnet
* Client waits for a configurable time for SEARCH responses
* 'sddp' command-line tool allow performing searches as well as running a standalone server

Installation
------------

### Prerequisites

**Python**: Python 3.8+ is required. See your OS documentation for instructions.

### From PyPi

The current released version of `sddp-discovery-protocol` can be installed with 

```bash
pip3 install sddp-discovery-protocol
```

### From GitHub

[Poetry](https://python-poetry.org/docs/master/#installing-with-the-official-installer) is required; it can be installed with:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Clone the repository and install sddp-discovery-protocol into a private virtualenv with:

```bash
cd <parent-folder>
git clone https://github.com/sammck/sddp-discovery-protocol.git
cd sddp-discovery-protocol
poetry install
```

You can then launch a bash shell with the virtualenv activated using:

```bash
poetry shell
```


Usage
=====

Command Line
------------

There is a single command tool `sddp` that is installed with the package.


#### Getting the package version
```bash
$ sddp version
0.1.0
$
```

#### Discovering devices on the local subnet

```bash
$ sddp search --help
usage: sddp search [-h] [--pattern PATTERN] [--wait-time WAIT_TIME] [-b BIND_ADDRESSES] [--include-error-responses]

Search for SDDP devices

options:
  -h, --help            show this help message and exit
  --pattern PATTERN     The device pattern to search for. Default: "*"
  --wait-time WAIT_TIME
                        The amount of time to wait for responses, in seconds. Default: 3.0
  -b BIND_ADDRESSES, --bind BIND_ADDRESSES
                        The local unicast IP address to bind to. May be repeated. Default: all local non-loopback unicast addresses.
  --include-error-responses
                        Include error responses in the output. Default: False
$ sddp search
[
  {
    "headers": {
      "Driver": "repeater_ip_lutron_radiora2.c4i",
      "From": "192.168.4.201:1902",
      "Host": "lutron-032e345c",
      "Manufacturer": "Lutron",
      "Max-Age": 1800,
      "Model": "RadioRA2 Main Repeater",
      "Primary-Proxy": "repeater_ip_lutron_radiora2",
      "Proxies": "repeater_ip_lutron_radiora2",
      "Type": "lutron:repeater_ip_lutron_radiora2"
    },
    "local_addr": "192.168.4.238:59060",
    "monotonic_time": 200338.359314361,
    "sddp_version": "1.0",
    "src_addr": "192.168.4.64:54838",
    "status": "OK",
    "status_code": 200,
    "utc_time": "2023-07-24T00:13:30.734784"
  },
  {
    "headers": {
      "Driver": "sonos.c4z",
      "From": "192.168.4.183:1902",
      "Host": "Sonos-347E5CD9C83A",
      "Manufacturer": "Sonos",
      "Max-Age": 1800,
      "Model": "Zoneplayer",
      "Primary-Proxy": "media_service",
      "Proxies": "media_service,amplifier",
      "Type": "sonos:Zoneplayer"
    },
    "local_addr": "192.168.4.238:59060",
    "monotonic_time": 200338.474668528,
    "sddp_version": "1.0",
    "src_addr": "192.168.4.183:55292",
    "status": "OK",
    "status_code": 200,
    "utc_time": "2023-07-24T00:13:30.850138"
  }
]
```

If you know the expected value of one or more response headers and are looking for a specific response, you
can speed up the search in the successful case by applying a header filter and limiting the responses
to 1; in this case the search will terminate as soon as the relevant response is received:

```bash
$ sddp search --max-responses 1 -F Type=JVCKENWOOD:Projector
{
  "headers": {
    "Driver": "projector_JVCKENWOOD_DLA-RS3100_NZ8.c4i",
    "From": "192.168.4.237:1902",
    "Host": "JVC_PROJECTOR-E0DADC152802",
    "Manufacturer": "JVCKENWOOD",
    "Max-Age": 1800,
    "Model": "DLA-RS3100_NZ8",
    "Primary-Proxy": "projector",
    "Proxies": "projector",
    "Type": "JVCKENWOOD:Projector"
  },
  "local_addr": "192.168.4.198:58941",
  "monotonic_time": 0.093766125,
  "sddp_version": "1.0",
  "src_addr": "192.168.4.237:1902",
  "status": "OK",
  "status_code": 200,
  "utc_time": "2023-07-24T22:23:54.175783"
}
```

#### Running an SDDP server
```bash
$ sddp server --help
usage: sddp server [-h] [--advertise-interval ADVERTISE_INTERVAL] [-H HEADERS] [-b BIND_ADDRESSES]

Run an SDDP server

options:
  -h, --help            show this help message and exit
  --advertise-interval ADVERTISE_INTERVAL
                        The interval at which to send device advertisements,
                        in seconds. Default: 2/3 of Max-Age header, or
                        1200 seconds (20 minutes)
  -H HEADERS, --header HEADERS
                        A <name>=<value> header to include in the device
                        advertisement. May be repeated.
  -b BIND_ADDRESSES, --bind BIND_ADDRESSES
                        The local unicast IP address to bind to.
                        May be repeated. Default: all local non-loopback
                        unicast addresses.
$ sddp --log-level=debug server
...
```

API
---

#### Discovering devices on the local subnet

```python
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
```

#### Running an SDDP server

```python
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
```

Known issues and limitations
----------------------------

* SDDP is a proprietary protocol defined by [Control4](https://www.control4.com/) with responders implemented by its
  smart-home business partners. The protocol is not standard and is not publicly documented. This
  package is a best effort to provide an open implementation of the protocol based on limited observation of
  network traffic. There is no way to know if the implementation is complete or totally accurate.

Getting help
------------

Please report any problems/issues [here](https://github.com/sammck/sddp-discovery-protocol/issues).

Contributing
------------

Pull requests welcome.

License
-------

sddp-discovery-protocol is distributed under the terms of the [MIT License](https://opensource.org/licenses/MIT).
The license applies to this file and other files in the [GitHub repository](http://github.com/sammck/sddp-discovery-protocol) hosting this file.

Authors and history
---------------------------

The author of sddp-discovery-protocol is [Sam McKelvie](https://github.com/sammck).
