import json
import array
import asyncio
from contextlib import AsyncExitStack
from asyncio_mqtt import Client, MqttError, Will
from ola.OlaClient import OlaClient
from pprint import pprint


CONFIG_TOPIC = "config"
COMMAND_TOPIC = "set"
STATUS_TOPIC = "status"
STATE_TOPIC = "state"
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"


async def mqtt_connect(conf):

    async with AsyncExitStack() as stack:

        # Keep track of the asyncio tasks that we create, so that
        # we can cancel them on exit
        tasks = set()

        async def cancel_tasks(tasks):
            for task in tasks:
                if task.done():
                    continue
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        stack.push_async_callback(cancel_tasks, tasks)

        # Create a LWT
        will = Will(conf["status_topic"], payload=STATUS_OFFLINE, retain=True, qos=2)

        # Connect to the MQTT broker
        print(f"Connecting to {conf['broker']}")
        client = Client(conf["broker"], will=will)
        await stack.enter_async_context(client)

        # Push a LWT-like message before disconnecting from the broker
        stack.push_async_callback(client.publish, conf["status_topic"], STATUS_OFFLINE, retain=True, qos=2)

        # Messages that doesn't match a filter will get logged here
        messages = await stack.enter_async_context(client.unfiltered_messages())
        task = asyncio.create_task(subscribe_event(conf, client, messages))
        tasks.add(task)

        print(f"Subscribing to {conf['command_topic']}")
        await client.subscribe(conf["command_topic"])

        # Publish config to HA
        task = asyncio.create_task(publish_config(conf, client))
        tasks.add(task)

        # Collect everything
        await asyncio.gather(*tasks)


async def publish_config(conf, client):

    print("CONFIG:")
    pprint(conf["config"])

    while True:

        print(f"Publish to {conf['config_topic']}")
        await client.publish(
            conf["config_topic"], json.dumps(conf["config"]), retain=True, qos=2
        )

        print(f"Publish to {conf['status_topic']}")
        await client.publish(conf["status_topic"], STATUS_ONLINE, retain=True, qos=2)

        await asyncio.sleep(conf['publish_interval'])


async def subscribe_event(conf, client, messages):

    # The state cache
    state = {
        "color": {"r": 0, "g": 0, "b": 0},
        "brightness": 0,
        "white_value": 0,
        "state": "OFF",
    }

    async for message in messages:
        print(f">>> TOPIC: {message.topic}")
        print(f"    PAYLOAD: {message.payload}")

        if message.topic == conf["command_topic"]:
            data = json.loads(message.payload)

            if "color" in data:
                state["color"] = data["color"]
            if "brightness" in data:
                state["brightness"] = data["brightness"]
            if "white_value" in data:
                state["white_value"] = data["white_value"]
            if "state" in data:
                state["state"] = data["state"]

            rgbw = [0] * 4
            if state["state"] == "ON":
                r, g, b = (
                    int(state["color"]["r"]),
                    int(state["color"]["g"]),
                    int(state["color"]["b"]),
                )
                w = int(state["white_value"])
                y = int(state["brightness"]) / 255
                rgbw = [int(r * y), int(g * y), int(b * y), w]

            print(f"    DMX {rgbw}")

            # Update the physical HW
            OlaClient().SendDmx(0, array.array("B", rgbw), None)

            # Publish the state
            await client.publish(conf["state_topic"], json.dumps(state))


async def main(conf):
    print(f"{conf['id']}: Running ola device")

    reconnect_interval = 3
    while True:
        try:
            await mqtt_connect(conf)
        except MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)


def init(conf):

    # MQTT DISCOVERY TOPIC
    conf["config"] = {
        "~": conf['topic'],
        "name": conf['name'],
        "device": conf['device'],
        "unique_id": conf['unique_id'],
        "command_topic": f"~/{COMMAND_TOPIC}",
        "state_topic": f"~/{STATE_TOPIC}",
        "availability_topic": f"~/{STATUS_TOPIC}",
        "schema": "json",
        "rgb": True,
        "white_value": True,
        "brightness": True,
    }

    # Other vars
    conf["config_topic"] = f"{conf['topic']}/{CONFIG_TOPIC}"
    conf["command_topic"] = f"{conf['topic']}/{COMMAND_TOPIC}"
    conf["status_topic"] = f"{conf['topic']}/{STATUS_TOPIC}"
    conf["state_topic"] = f"{conf['topic']}/{STATE_TOPIC}"

    # Return the main function coro
    return main(conf)
