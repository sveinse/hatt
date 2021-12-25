import asyncio
import serial_asyncio
import serial
from queue import Queue
import asyncio_mqtt as mqtt
from pprint import pprint

from . import hatt


# HW50 Protocol
# 38500, 8 bits, even parity, one stop bit
# 8 byte packets
#     B0: SOF 0xA9
#     B1: ITEM
#     B2: ITEM
#     B3: TYPE
#     B4: DATA
#     B5: DATA
#     B6: CHECKSUM (OR of B1-B5)
#     B7: EOF 0x9A

# FRAMING
FRAMESIZE = 8
SOF = 0xA9
EOF = 0x9A

# REQUEST/RESPONSE TYPES
SET_RQ = 0x00
GET_RQ = 0x01
GET_RS = 0x02
ACK_RS = 0x03
TYPES = {
    SET_RQ: "SET.rq",
    GET_RQ: "GET.rq",
    GET_RS: "GET.rs",
    ACK_RS: "ACK.rs",
}

# RESPONSE TYPES
ACK_OK = 0x0000
NAK_UNKNOWNCOMMAND = 0x0101
NAK_SIZEERR = 0x0104
NAK_SELECTERR = 0x0105
NAK_RANGEOVER = 0x0106
NAK_NA = 0x010A
NAK_CHECKSUM = 0xF010
NAK_FRAMINGERR = 0xF020
NAK_PARITYERR = 0xF030
NAK_OVERRUN = 0xF040
NAK_OTHERERR = 0xF050
RESPONSES = {
    ACK_OK: "OK",
    NAK_UNKNOWNCOMMAND: "Unknown command",
    NAK_SIZEERR: "Frame size error",
    NAK_SELECTERR: "Select error",
    NAK_RANGEOVER: "Range over error",
    NAK_NA: "Not applicable command",
    NAK_CHECKSUM: "Checksum error",
    NAK_FRAMINGERR: "Framing error",
    NAK_PARITYERR: "Parity error",
    NAK_OVERRUN: "Overrun error",
    NAK_OTHERERR: "Other error"
}

# ITEMS for picture
CALIB_PRESET = 0x0002
CONTRAST = 0x0010
BRIGHTNESS = 0x0011
COLOR = 0x0012
HUE = 0x0013
SHARPNESS = 0x0014
COLOR_TEMP = 0x0017
LAMP_CONTROL = 0x001A
CONTRAST_ENHANCER = 0x001C
ADVANCED_IRIS = 0x001D
REAL_COLOR_PROCESSING = 0x001E
FILM_MODE = 0x001F
GAMMA_CORRECTION = 0x0022
NR = 0x0025
COLOR_SPACE = 0x003B
USER_GAIN_R = 0x0050
USER_GAIN_G = 0x0051
USER_GAIN_B = 0x0052
USER_BIAS_R = 0x0053
USER_BIAS_G = 0x0054
USER_BIAS_B = 0x0055
IRIS_MANUAL = 0x0057
FILM_PROJECTION = 0x0058
MOTION_ENHANCER = 0x0059
XV_COLOR = 0x005A
REALITY_CREATION = 0x0067
RC_RESOLUTION = 0x0068
RC_NOISEFILTER = 0x0069
MPEG_NR = 0x006C

# ITEMS for screen
ASPECT = 0x0020
OVERSCAN = 0x0023
SCREEN_AREA = 0x0024

# ITEMS for setup
INPUT = 0x0001
MUTE = 0x0030
HDMI1_DYNRANGE = 0x006E
HDMI2_DYNRANGE = 0x006F
SETTINGS_LOCK = 0x0073

# ITEMS for 3D
DISPSEL_3D = 0x0060
FORMAT_3D = 0x0061
FORMAT_DEPTH = 0x0062
EFFECT_3D = 0x0063
GLASS_BRIGHTNESS = 0x0065

# ITEMS for status
STATUS_ERROR = 0x0101
STATUS_POWER = 0x0102
LAMP_TIMER = 0x0113
STATUS_ERROR2 = 0x0125

# ITEMS for IR
IRCMD = 0x1700
IRCMD2 = 0x1900
IRCMD3 = 0x1B00
IRCMD_MASK = 0xFF00

IR_PWRON = IRCMD | 0x2E
IR_PWROFF = IRCMD | 0x2F

IR_MUTE = IRCMD | 0x24

IR_STATUSON = IRCMD | 0x25
IR_STATUSOFF = IRCMD | 0x26

# LIST OF ALL ITEMS
ITEMS = {
    STATUS_ERROR: "Status Error",
    STATUS_POWER: "Status Power",
    LAMP_TIMER: "Lamp Timer",
    STATUS_ERROR2: "Status Error2",
    IR_PWROFF: "Power Off (IR)",
    IR_PWRON: "Power On (IR)",
    CALIB_PRESET: "Preset",
}

# DATA FIELDS
CALIB_PRESET_CINEMA1 = 0x0000
CALIB_PRESET_CINEMA2 = 0x0001
CALIB_PRESET_REF = 0x0002
CALIB_PRESET_TV = 0x0003
CALIB_PRESET_PHOTO = 0x0004
CALIB_PRESET_GAME = 0x0005
CALIB_PRESET_BRTCINE = 0x0006
CALIB_PRESET_BRTTV = 0x0007
CALIB_PRESET_USER = 0x0008

CALIB_PRESETS = {
    CALIB_PRESET_CINEMA1: "Cinema Film 1",
    CALIB_PRESET_CINEMA2: "Cinema Film 2",
    CALIB_PRESET_REF: "Reference",
    CALIB_PRESET_TV: "TV",
    CALIB_PRESET_PHOTO: "Photo",
    CALIB_PRESET_GAME: "Game",
    CALIB_PRESET_BRTCINE: "Bright Cinema",
    CALIB_PRESET_BRTTV: "Bright TV",
    CALIB_PRESET_USER: "User",
}

STATUS_ERROR_OK = 0x0000
STATUS_ERROR_LAMP = 0x0001
STATUS_ERROR_FAN = 0x0002
STATUS_ERROR_COVER = 0x0004
STATUS_ERROR_TEMP = 0x0008
STATUS_ERROR_D5V = 0x0010
STATUS_ERROR_POWER = 0x0020
STATUS_ERROR_TEMP = 0x0040
STATUS_ERROR_NVM = 0x0080

STATUS_ERRORS = {
    STATUS_ERROR_OK: "No Error",
    STATUS_ERROR_LAMP: "Lamp Error",
    STATUS_ERROR_FAN: "Fan Error",
    STATUS_ERROR_COVER: "Cover Error",
    STATUS_ERROR_TEMP: "Temp Error",
    STATUS_ERROR_D5V: "D5V Error",
    STATUS_ERROR_POWER: "Power Error",
    STATUS_ERROR_TEMP: "Temp Warning",
    STATUS_ERROR_NVM: "NVM Data Error",
}

STATUS_POWER_STANDBY = 0x0000
STATUS_POWER_STARTUP = 0x0001
STATUS_POWER_STARTUPLAMP = 0x0002
STATUS_POWER_POWERON = 0x0003
STATUS_POWER_COOLING1 = 0x0004
STATUS_POWER_COOLING2 = 0x0005
STATUS_POWER_SAVINGCOOLING1 = 0x0006
STATUS_POWER_SAVINGCOOLING2 = 0x0007
STATUS_POWER_SAVINGSTANDBY = 0x0008

STATUS_POWERS = {
    STATUS_POWER_STANDBY: "Standby",
    STATUS_POWER_STARTUP: "Start Up",
    STATUS_POWER_STARTUPLAMP: "Startup Lamp",
    STATUS_POWER_POWERON: "Power On",
    STATUS_POWER_COOLING1: "Cooling1",
    STATUS_POWER_COOLING2: "Cooling2",
    STATUS_POWER_SAVINGCOOLING1: "Saving Cooling1",
    STATUS_POWER_SAVINGCOOLING2: "Saving Cooling2",
    STATUS_POWER_SAVINGSTANDBY: "Saving Standby",
}

STATUS_ERROR2_OK = 0x0000
STATUS_ERROR2_HIGHLAND = 0x0020

STATUS_ERRORS2 = {
    STATUS_ERROR2_OK: "No Error",
    STATUS_ERROR2_HIGHLAND: "Highland Warning",
}


class FrameError(Exception):
    pass
class CommandError(Exception):
    pass


def dump(data):
    ''' Return a printout string of data '''
    msg = bytearray(data)
    s = ' '.join(['%02x' %(x) for x in msg])
    return "(%s) %s" %(len(data), s)


def dumptext(data):
    ''' Return a HW50 frame printout as text '''
    b = bytearray(data)

    item = b[1]<<8 | b[2]
    cmd = b[3]
    data = b[4]<<8 | b[5]

    s1 = TYPES.get(cmd, '???')
    s2 = ''
    s3 = ITEMS.get(item, '???')
    if cmd == GET_RQ:
        s2 = '%04x "%s"' %(item, s3)
    elif cmd in (SET_RQ, GET_RS):
        s2 = '%04x "%s" = %04x' %(item, s3, data)
    elif cmd == ACK_RS:
        s2 = RESPONSES.get(item, '???')
    return s1 + ' ' + s2


def decode_hw50frame(frame, response_frame=True):
    ''' Decode an HW50 frame '''
    b = bytearray(frame)

    if len(frame) != FRAMESIZE:
        raise FrameError("Incomplete frame")
    if b[0] != SOF:
        raise FrameError("Wrong SOF field")
    if b[7] != EOF:
        raise FrameError("Wrong EOF field")

    c = 0
    for x in range(1, 6):
        c |= b[x]
    if b[6] != c:
        raise FrameError("Checksum failure")

    item = b[1]<<8 | b[2]
    cmd = b[3]
    data = b[4]<<8 | b[5]

    if response_frame:
        if cmd == ACK_RS:
            if item not in RESPONSES:
                raise FrameError("Unknown ACK/NAK response error")
        elif cmd == GET_RS:
            pass
        else:
            raise FrameError("Unknown response type")

    return (item, cmd, data)


def encode_hw50frame(item, cmd, data):
    ''' Return an encoded frame '''
    b = bytearray(b"\x00" * FRAMESIZE)

    b[0] = SOF
    b[1] = (item&0xFF00)>>8
    b[2] = (item&0xFF)
    b[3] = cmd
    b[4] = (data&0xFF00)>>8
    b[5] = (data&0xFF)

    c = 0
    for x in range(1, 6):
        c |= b[x]
    b[6] = c
    b[7] = EOF

    return b


class Hw50(asyncio.Protocol):
    timeout = 3.5

    @classmethod
    async def connect(cls, device):
        loop = asyncio.get_running_loop()
        return await serial_asyncio.create_serial_connection(loop, cls,
            device,
            baudrate=38500,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

    def __init__(self):
        self.queue = Queue()

    def connection_made(self, transport):
        self.transport = transport
       #print('connection_made', transport)
        self.connected = True
        self.rxbuffer = bytearray()
        self.lastmsg = None

    def connection_lost(self, exc):
        #print('connection_lost')
        self.connected = False

    #def pause_writing(self):
    #    print('pause_writing')
    #    print(self.transport.get_write_buffer_size())

    #def resume_writing(self):
    #    print(self.transport.get_write_buffer_size())
    #    print('resume_writing')

    def data_received(self, data):
        #print('data_received', repr(data))

        #self.log.debug('{_rawin}', rawin=data)
        msg = bytearray(data)
        self.rxbuffer += msg

        # Search for data frames in the incoming data buffer. Search for SOF and EOF markers.
        # It will only iterate if the buffer is large enough for a complete frame
        buf = self.rxbuffer
        for x in range(0, len(buf)-FRAMESIZE+1):

            # Search for SOF and EOF markers
            if buf[x] == SOF and buf[x+FRAMESIZE-1] == EOF:

                try:
                    # Decode the response-frame
                    frame = buf[x:x+FRAMESIZE]
                    print(f"     >>>  {dump(frame)} - {dumptext(frame)}")
                    item, cmd, data = decode_hw50frame(frame)

                except FrameError as e:

                    # Frame decode fails, do iteration
                    print(f"Decode failure: {e}")
                    continue

                # Consume all data up until the frame (including pre-junk) and
                # save the data after the frame for later processing
                self.rxbuffer = buf[x+FRAMESIZE:]
                if x > 0 or len(self.rxbuffer) > 0:
                    print(f"Discarded junk in data, '{dump(buf[:x])}' before, '{dump(self.rxbuffer)}' after")

                # Process the reply frame
                if self.lastmsg:

                    # Cancel the timeout task
                    #send_item, send_cmd, _ = decode_hw50frame(self.lastmsg, response_frame=False)
                    self.lastmsg = None
                    self.timer.cancel()

                    # Treat either A) Unknown frame type commands or
                    #              B) ACK_RS types with non-ACK_OK responses
                    # as errors
                    #if cmd != send_cmd:
                    #    self.future.set_exception(FrameError("Invalid response"))
                    if cmd not in TYPES or (cmd == ACK_RS and item != ACK_OK):
                        self.future.set_exception(CommandError(RESPONSES.get(item, item)))
                    else:
                        self.future.set_result(data)

                    # Proceed to the next command
                    self.send_next()
                    return

                # Not interested in the received message
                print("-IGNORED-")

    def send_next(self):
        # Don't send if communication is pending
        if self.lastmsg:
            return

        while self.queue.qsize():
            future, msg, item = self.queue.get(False)

            # Send the command
            print(f"     <<<  {dump(msg)} - {dumptext(msg)}")
            self.transport.write(msg)

            # Prepare for reply where applicable
            ircmd = item & IRCMD_MASK

            # IR-commands does not reply, so they can be replied to immediately
            # and can proceed to next command
            if ircmd in (IRCMD, IRCMD2, IRCMD3):
                future.set_result(None)
                continue

            # Expect reply, setup timeout and return
            self.lastmsg = msg
            self.future = future
            self.timer = asyncio.create_task(self.timeout_keeper())
            return

    async def timeout_keeper(self):
        await asyncio.sleep(self.timeout)
        # The timeout response is to fail the request and proceed with the next command
        print(f"Command {dumptext(self.lastmsg)} timed out")
        self.lastmsg = None
        self.future.set_exception(TimeoutError())
        self.send_next()

    def command(self, item, cmd=GET_RQ, data=0x0):
        # Compile next request
        msg = encode_hw50frame(item, cmd, data)
        future = asyncio.get_running_loop().create_future()
        self.queue.put((future, msg, item))
        self.send_next()
        return future

    # -- Composite commands --

    async def get_status_error(self):
        status = await self.command(STATUS_ERROR)
        if status == STATUS_ERROR_OK:
            return STATUS_ERRORS[STATUS_ERROR_OK]
        return [t for s, t in STATUS_ERRORS.items() if s & status]

    async def get_status_power(self):
        status = await self.command(STATUS_POWER)
        return STATUS_POWERS.get(status, "Uknown status")

    async def power_on(self):
        await self.command(IR_PWRON, cmd=SET_RQ)

    async def power_off(self):
        await self.command(IR_PWROFF, cmd=SET_RQ)


class Hw50Emulator:

    def __init__(self, protocol):
        self.protocol = protocol
        self.power = STATUS_POWER_STANDBY
        protocol.connection_made(self)

    def reply(self, item, cmd, data, delay=0.1):
        async def send(msg):
            await asyncio.sleep(delay)
            print(f"HW50 RX:  {dump(msg)}")
            self.protocol.data_received(msg)
        asyncio.create_task(send(encode_hw50frame(item, cmd, data)))

    def write(self, msg):
        print(f"HW50 TX:  {dump(msg)}")
        item, cmd, data = decode_hw50frame(msg, response_frame=False)

        if item == STATUS_POWER:
            self.reply(item, GET_RS, self.power)
        elif item == STATUS_ERROR:
            self.reply(item, GET_RS, STATUS_ERROR_OK)
        elif item == STATUS_ERROR2:
            self.reply(item, GET_RS, STATUS_ERROR2_OK)
        elif item == LAMP_TIMER:
            self.reply(item, GET_RS, 100)
        elif item == IR_PWRON:
            asyncio.create_task(self.poweron())
        elif item == IR_PWROFF:
            asyncio.create_task(self.poweroff())
        else:
            self.reply(NAK_UNKNOWNCOMMAND, ACK_RS, 0)

    async def poweron(self):
        self.power = STATUS_POWER_STARTUPLAMP
        await asyncio.sleep(5)
        self.power = STATUS_POWER_POWERON

    async def poweroff(self):
        self.power = STATUS_POWER_COOLING1
        await asyncio.sleep(5)
        self.power = STATUS_POWER_COOLING2
        await asyncio.sleep(5)
        self.power = STATUS_POWER_STANDBY



class Hw50Hatt(hatt.Hatt):

    def __init__(self, conf, hw50):
        super().__init__(conf)

        self.hw50 = hw50

        # MQTT DISCOVERY TOPIC
        conf["config"] = {
            "~": conf['topic'],
            "name": conf['name'],
            "device": conf['device'],
            "unique_id": conf['unique_id'],
            "command_topic": f"~/{self.COMMAND_TOPIC}",
            "availability_topic": f"~/{self.STATUS_TOPIC}",
            "state_topic": f"~/{self.STATE_TOPIC}",
            "json_attributes_topic": f"~/{self.STATE_TOPIC}",
            "value_template": "{{ value_json.state }}",
        }

        self.state = {
            "power_state": "Unknown",
            "status": "Unknown",
            "state": "OFF",
            "lamp_timer": 0,
        }
        self.queue = asyncio.Queue()

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

            if topic == self.command_topic:
                state = self.state['state']

                if payload == b'ON' and state == 'OFF':

                    self.state['state'] = 'ON'
                    await self.hw50.power_on()
                    await asyncio.sleep(1)
                    await self.queue.put(None)

                elif payload == b'OFF' and state == 'ON':

                    self.state['state'] = 'OFF'
                    await self.hw50.power_off()
                    await asyncio.sleep(1)
                    await self.queue.put(None)

    async def status_publisher(self):

        # Wait until the config has been sent
        await self.config_event.wait()

        while True:
            try:
                interval = self.conf['status_interval']
                do_full_status = True

                power = await self.hw50.get_status_power()

                if power not in (
                    STATUS_POWERS[STATUS_POWER_STANDBY],
                    STATUS_POWERS[STATUS_POWER_SAVINGSTANDBY],
                    STATUS_POWERS[STATUS_POWER_POWERON],
                ):
                    interval = 1
                    do_full_status = False

                self.state['power_state'] = power
                if power in (
                    STATUS_POWERS[STATUS_POWER_STANDBY],
                    STATUS_POWERS[STATUS_POWER_SAVINGSTANDBY],
                ):
                    self.state['state'] = 'OFF'
                if power in (
                    STATUS_POWERS[STATUS_POWER_POWERON],
                ):
                    self.state['state'] = 'ON'

                if do_full_status:
                    status = await self.hw50.get_status_error()
                    self.state['status'] = status

                    lamp = await self.hw50.command(LAMP_TIMER)
                    self.state['lamp_timer'] = lamp

                await self.publish_status(self.STATUS_ONLINE)

            except TimeoutError:
                await self.publish_status(self.STATUS_OFFLINE)

            finally:
                await self.publish_state()

            try:
                await asyncio.wait_for(self.queue.get(), interval)
            except asyncio.TimeoutError:
                pass


async def main(conf):
    print(f"{conf['id']}: Running hw50 device")

    # Open protocol handler
    _, hw50 = await Hw50.connect(conf['port'])

    # Protocol testing
    #hw50 = Hw50()
    #Hw50Emulator(hw50)

    reconnect = False
    reconnect_interval = conf['reconnect_interval']
    while True:
        try:
            if reconnect:
                await asyncio.sleep(reconnect_interval)

            await Hw50Hatt(conf, hw50).main()

        except mqtt.MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            reconnect = True
