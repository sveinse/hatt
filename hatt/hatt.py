import asyncio
import contextlib
import json
from pprint import pprint
import asyncio_mqtt as mqtt


async def cancel_task(task):
    if not task or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class Hatt:

    CONFIG_TOPIC = "config"
    COMMAND_TOPIC = "set"
    STATUS_TOPIC = "status"
    STATE_TOPIC = "state"
    #ATTRIBUTE_TOPIC = "attribute"
    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    HA_STATUS = "homeassistant/status"

    def __init__(self, conf):
        self.conf = conf

        self.status = self.STATUS_OFFLINE
        self.state = None
        self.laststate = None

        self.config_topic = f"{conf['topic']}/{self.CONFIG_TOPIC}"
        self.command_topic = f"{conf['topic']}/{self.COMMAND_TOPIC}"
        self.status_topic = f"{conf['topic']}/{self.STATUS_TOPIC}"
        self.state_topic = f"{conf['topic']}/{self.STATE_TOPIC}"
        #self.attribute_topic = f"{conf['topic']}/{ATTRIBUTE_TOPIC}"

        self.config_task = None
        self.status_task = None

        self.config_event = asyncio.Event()

    async def main(self):

        async with contextlib.AsyncExitStack() as stack:

            async def _cancel_tasks():
                await cancel_task(self.config_task)
                await cancel_task(self.status_task)

            # Keep track of the asyncio tasks that we create, so that
            # we can cancel them on exit
            stack.push_async_callback(_cancel_tasks)

            # Create a LWT
            will = mqtt.Will(self.status_topic,
                             payload=self.STATUS_OFFLINE, retain=True, qos=2)

            # Connect to the MQTT broker
            print(f"Connecting to {self.conf['broker']}")
            client = mqtt.Client(self.conf["broker"], will=will)
            await stack.enter_async_context(client)
            self.mqtt = client

            # Push a LWT-like message before disconnecting from the broker
            stack.push_async_callback(self.publish, will.topic,
                                      payload=will.payload,
                                      retain=will.retain, qos=will.qos)

            # Handle every subscribed message using unfiltered_messages()
            # Use client.filtered_message() if only a subset is wanted
            messages = await stack.enter_async_context(client.unfiltered_messages())

            print(f"Subscribing to {self.command_topic}")
            await client.subscribe(self.command_topic)
            await client.subscribe(self.HA_STATUS)

            # Create the publisher tasks
            self.config_task = asyncio.create_task(self.config_publisher())
            self.status_task = asyncio.create_task(self.status_publisher())

            # Start receiving messages
            await self.message_handler(messages)

    async def restart_config_publisher(self):
        self.config_event.clear()
        await cancel_task(self.config_task)
        self.config_task = asyncio.create_task(self.config_publisher())
        await self.config_event.wait()

    async def config_publisher(self):

        print("CONFIG:")
        pprint(self.conf["config"])

        # Ensure state and status are present before pushing the config
        await self.publish_state(force=True)
        await self.publish_status(self.status, force=True)

        while True:

            # Publish the config
            await self.publish_config()

            # Signal that the config has been sent
            self.config_event.set()

            await asyncio.sleep(self.conf['publish_interval'])

    async def status_publisher(self):

        # Ensure the config has been sent
        await self.config_event.wait()

        while True:

            # Publish the status
            # FIXME: Sets status to online. Should be done elsewhere?
            await self.publish_status(self.STATUS_ONLINE)

            await asyncio.sleep(self.conf['status_interval'])

    async def message_handler(self, messages):

        # Wait until the config has been sent
        await self.config_event.wait()

        # Loop over the subscriptions
        async for message in messages:
            topic = message.topic
            payload = message.payload

            print(f">>> TOPIC: {topic}")
            print(f"    PAYLOAD: {payload}")

            if topic == self.HA_STATUS and payload == b'online':
                await self.restart_config_publisher()

    async def publish(self, topic, payload, **kwargs):
        print(f"<<< PUBLISH: {topic}")
        print(f"    PAYLOAD: {payload}")
        return await self.mqtt.publish(topic, payload, **kwargs)

    async def publish_config(self):
        return await self.publish(
            self.config_topic, json.dumps(self.conf['config']), retain=True, qos=2
        )

    async def publish_status(self, status=STATUS_OFFLINE, force=False):
        if force or self.status != status:
            self.status = status
            return await self.publish(
                self.status_topic, status, retain=True, qos=2
            )

    async def publish_state(self, force=False):
        if force or self.state != self.laststate:
            self.laststate = self.state.copy()
            return await self.publish(
                self.state_topic, json.dumps(self.state), retain=True
            )
