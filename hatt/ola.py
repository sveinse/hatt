import json
import array
import asyncio
import asyncio_mqtt as mqtt
from ola.OlaClient import OlaClient
from pprint import pprint

from . import hatt


class Array:
    ''' Hack as ola relies on calling array.array().tostring()
        which recent py doesn't support
    '''
    def __init__(self, data):
        self.d = data
    def tostring(self):
        return array.array("B", self.d).tobytes()


class OlaHatt(hatt.Hatt):

    def __init__(self, conf):
        super().__init__(conf)

        # MQTT DISCOVERY TOPIC
        conf["config"] = {
            "~": conf['topic'],
            "name": conf['name'],
            "device": conf['device'],
            "unique_id": conf['unique_id'],
            "command_topic": f"~/{self.COMMAND_TOPIC}",
            "state_topic": f"~/{self.STATE_TOPIC}",
            "availability_topic": f"~/{self.STATUS_TOPIC}",
            "schema": "json",
            "rgb": True,
            "white_value": True,
            "brightness": True,
            "color_temp": False
            #"color_mode": True,
            #"supported_color_modes": ["rgbw"]
        }

        self.state = {
            "color": {"r": 0, "g": 0, "b": 0},
            "brightness": 0,
            "white_value": 0,
            "state": "OFF",
        }

    async def message_handler(self, messages):

        # Wait until the config has been sent
        await self.config_event.wait()

        # Loop over the subscriptions
        async for message in messages:
            topic = message.topic
            payload = message.payload

            print(f">>> TOPIC: {topic}")
            print(f"    PAYLOAD: {payload}")

            if topic == self.HA_STATUS and payload == b"online":
                await self.restart_config_publisher()

            if topic == self.command_topic:
                state = self.state
                data = json.loads(payload)

                # Copy the select vars from the data to the local state
                for var in ("color", "brightness", "white_value", "state"):
                    if var in data:
                        state[var] = data[var]

                print(f"    STATE: {state}")

                # Default everything off
                dmx = [0] * 4

                if state["state"] == "ON":
                    r = int(state["color"]["r"])
                    g = int(state["color"]["g"])
                    b = int(state["color"]["b"])
                    w = int(state["white_value"])
                    y = int(state["brightness"]) / 255

                    # If brightness is set but no color, set it to pure white
                    if y > 0 and r == 0 and g == 0 and b == 0:
                        r = g = b = 255

                    # RGBW values are hardcoded into DMX channels 0-3
                    dmx = [int(r * y), int(g * y), int(b * y), w]

                # Update the DMX data. Universe 0
                print(f"    DMX {dmx}")
                OlaClient().SendDmx(0, Array(dmx), None)

                await self.publish_state()


async def main(conf):
    print(f"{conf['id']}: Running ola device")

    reconnect = False
    reconnect_interval = conf['reconnect_interval']
    while True:
        try:
            if reconnect:
                await asyncio.sleep(reconnect_interval)

            await OlaHatt(conf).main()

        except mqtt.MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            reconnect = True
