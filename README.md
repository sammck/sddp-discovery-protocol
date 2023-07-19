jvc-projector: Client library for control of JVC projectors over TCP/IP
=================================================

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Latest release](https://img.shields.io/github/v/release/sammck/jvc-projector.svg?style=flat-square&color=b44e88)](https://github.com/sammck/jvc-projector/releases)

A tool and API for controlling JVC projectors via their proprietary TCP/IP protocol.

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

Python package `jvc-projector` provides a command-line tool as well as a runtime API for controlling many JVC projector models that include
an Ethernet port for TCP/IP control.

Some key features of jvc-projector:

* JSON results
* Query projector model
* Query power status
* Power on
* Power standby
* Wait for warmup/cooldown

Installation
------------

### Prerequisites

**Python**: Python 3.8+ is required. See your OS documentation for instructions.

### From PyPi

The current released version of `jvc-projector` can be installed with 

```bash
pip3 install jvc-projector
```

### From GitHub

[Poetry](https://python-poetry.org/docs/master/#installing-with-the-official-installer) is required; it can be installed with:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Clone the repository and install jvc-projector into a private virtualenv with:

```bash
cd <parent-folder>
git clone https://github.com/sammck/jvc-projector.git
cd jvc-projector
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

There is a single command tool `jvc-projector` that is installed with the package.


API
---

TBD

Known issues and limitations
----------------------------

* Import/export are not yet supported.

Getting help
------------

Please report any problems/issues [here](https://github.com/sammck/jvc-projector/issues).

Contributing
------------

Pull requests welcome.

License
-------

jvc-projector is distributed under the terms of the [MIT License](https://opensource.org/licenses/MIT).  The license applies to this file and other files in the [GitHub repository](http://github.com/sammck/jvc-projector) hosting this file.

Authors and history
---------------------------

The author of jvc-projector is [Sam McKelvie](https://github.com/sammck).
