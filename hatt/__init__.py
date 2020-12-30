
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
    parser.add_argument('run', metavar='NAMES', nargs="*", help=f'Devices to run')

    opts = parser.parse_args()

    # Read config
    with open(opts.conf, 'r') as f:
        conf = json.load(f)

    devices = opts.run or conf.get('run', [])
    if not devices:
        parser.error(f"Missing device")

    mains = []
    for device in devices:
        if device not in conf.get('devices',{}):
            parser.error(f"{opts.conf}: No device '{device}' found")

        data = conf['devices'][device]
        data['id'] = device
        data['broker'] = conf['broker']

        plugin = import_module('hatt.' + data['type'])
        mains.append(plugin.init(data))

    # Run the main loop
    asyncio.run(amain(mains))
