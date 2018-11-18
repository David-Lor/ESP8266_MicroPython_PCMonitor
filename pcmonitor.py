import ujson
import sys
from umqtt.simple import MQTTClient
from machine import Pin, reset
from time import sleep

# Misc functions

def pinout(esp8266pin):
    """Return the numerical pinout equivalence of the ESP8266/NodeMCU numeration (i.e. D3=0),
    using the equivalences defined on the esp8266_pinout.json file.
    """
    return PINOUT[esp8266pin]

def load_json(filename):
    """Load and parse a JSON file.
    """
    file = open(filename, "r")
    json_str = file.read().replace("'", '"')
    file.close()
    return ujson.loads(json_str)

def ftopic(tail):
    """Get the full MQTT Topic, concatenating Base topic and Tail topic.
    All topics are defined on the pcmonitor_settings.json file.
    """
    return TOPIC["base"] + TOPIC[tail]


# Pin misc functions
last_power_led = None
def power_led_interrupt_callback(pin):
    global last_power_led
    value = pin.value()
    if value != last_power_led:
        last_power_led = value
        if value:
            payload = "ON"
        else:
            payload = "OFF"
        client.publish(
            topic=ftopic("raw_powerled_stat").encode(),
            msg=payload.encode(),
            retain=False
        )


# Load JSON files
SETTINGS = load_json("pcmonitor_settings.json")
SETTINGS_MQTT = SETTINGS["MQTT"]
TOPIC = SETTINGS_MQTT["topics"]
SETTINGS_PINOUT = SETTINGS["Pinout"]
PINOUT = load_json("esp8266_pinout.json")

# Pinout
POWER_SWITCH = Pin(pinout(SETTINGS_PINOUT["PowerSwitch"]), Pin.OUT)
POWER_SWITCH.off()
POWER_LED = Pin(pinout(SETTINGS_PINOUT["PowerLED"]), Pin.IN)
POWER_LED.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=power_led_interrupt_callback)

# MQTT Disconnect function

def disconnect():
    client.publish(
        topic=ftopic("stat").encode(),
        msg="OFF".encode(),
        retain=True
    )
    client.disconnect()

# MQTT callback
keep_looping = True
def sub_callback(topic, payload):
    global keep_looping
    topic = topic.decode()
    payload = payload.decode().upper()
    print("Received MQTT (Topic:{}) - {}".format(topic, payload))
    if topic == ftopic("raw_powerswitch_cmd"):
        if payload == "ON" or payload == "1":
            print("Manual power switch ON")
            POWER_SWITCH.on()
        elif payload == "OFF" or payload == "0":
            print("Manual power switch OFF")
            POWER_SWITCH.off()
    elif topic == ftopic("cmd"):
        if payload == "STOP":
            print("Manual Loop STOP")
            keep_looping = False
        elif payload == "RESET" or payload == "REBOOT":
            print("Manual Reboot")
            disconnect()
            reset()


# MQTT startup
client = MQTTClient(
    client_id=SETTINGS_MQTT["name"],
    server=SETTINGS_MQTT["broker"],
    port=SETTINGS_MQTT["port"],
    user=SETTINGS_MQTT["user"] if SETTINGS_MQTT["user"] else None,
    password=SETTINGS_MQTT["password"] if SETTINGS_MQTT["password"] else None#,
    #keepalive=SETTINGS_MQTT["keepalive"]
)
client.set_callback(sub_callback)
client.set_last_will(
    topic=ftopic("stat").encode(),
    msg="OUTOFSYNC".encode(),
    retain=True
)
client.connect()
client.subscribe(topic=(TOPIC["base"]+"#").encode())
client.publish(
    topic=ftopic("stat").encode(),
    msg="ON".encode(),
    retain=True
)
print("PC Monitor MQTT client connected!")


# MQTT&Main Loop
def loop():
    global keep_looping
    keep_looping = True
    
    print("Loop started")
    while keep_looping:
        try:
            client.wait_msg()
        except KeyboardInterrupt:
            break
        except Exception as ex:
            print("Error on loop:")
            sys.print_exception(ex)
            sleep(2)
    
    # MQTT Disconnect when loop ends
    disconnect()
