
import argparse
import json
from importlib import import_module
import asyncio


PROG = "hatt"
DESCRIPTION = "hatt"
CONFFILE = 'hatt.json'


async def amain(coros):
    await asyncio.gather(*[asyncio.create_task(co) for co in coros])


def main():

    from pprint import pprint

    # Parse arguments
    parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION)
    parser.add_argument('--conf', '--config', '-c', metavar='FILE', help=f'Configuration file. Default: {CONFFILE}',
                        default=CONFFILE)
    parser.add_argument('devices', metavar='NAMES', nargs="*", help='Devices to start')

    opts = parser.parse_args()

    # Read config
    with open(opts.conf, 'r') as f:
        conf = json.load(f)

    devices = opts.devices or conf.get('start', [])
    if not devices:
        parser.error("Missing device")

    mains = []
    for device in devices:
        if device not in conf.get('devices', {}):
            parser.error(f"{opts.conf}: No device '{device}' found")

        data = conf['devices'][device]
        data['id'] = device
        data['broker'] = conf['broker']
        data['reconnect_interval'] = conf.get('reconnect_interval', 3)

        plugin = import_module('hatt.' + data['module'])
        mains.append(plugin.main(data))

    # Run the main loop
    asyncio.run(amain(mains))
