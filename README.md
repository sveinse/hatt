# Home Assistant MQTT device interfaces

This repo contains a light-weight python interface from various devices to
Home Assistant using MQTT. The tool is written in Python 3 and uses asyncio.
It is controlled by a json configuration files which selects which modules
to use and connect.


## Modules

* `hw50` - Serial port interface to Sony VPL-HW50ES projector. It registers as
           a switch which will turn the projector on and off. It reports back the
           status of the device, including number of lamp runtime hours.

* `ola`  - Open Lighting Architecture interface. Used for accessing led-strip
           lights from DMX. It is currently hardcoded for giving a interface to
           DMX universe 0 on address 0-3 (rgbw).


## Configuration

`hatt` is configured by a json file. Please see [`hatt.json.example`](hatt.json.example)


## Installation

To install, use Python's virtual environment:

    $ cd hatt
    $ python3 -mvenv venv
    $ venv/bin/python -mpip install --upgrade pip wheel setuptools
    $ venv/bin/pip install .[hw50,ola]  # Select which dependencies to install

To run, call the hatt executable and point to a config file:

    $ venv/bin/hatt -c config.json
