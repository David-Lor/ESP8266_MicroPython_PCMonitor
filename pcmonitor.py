import ujson
from umqtt.simple import MQTTClient
from machine import Pin, reset

# Misc functions

def pinout(esp8266pin):
    return PINOUT[esp8266pin]

def load_json(filename):
    file = open(filename, "r")
    json_str = file.read().replace("'", '"')
    file.close()
    return ujson.loads(json_str)

def ftopic(tail):
    return TOPIC["base"] + TOPIC[tail]

# Load JSON files
SETTINGS = load_json("pcmonitor_settings.json")
SETTINGS_MQTT = SETTINGS["MQTT"]
TOPIC = SETTINGS_MQTT["topics"]
SETTINGS_PINOUT = SETTINGS["Pinout"]
PINOUT = load_json("esp8266_pinout.json")

# Pinout
POWERSWITCH = Pin(pinout(SETTINGS_PINOUT["PowerSwitch"]), Pin.OUT)

# MQTT
keep_looping = True
def sub_callback(topic, payload):
    global keep_looping
    topic = topic.decode()
    payload = payload.decode().upper()
    print("Received MQTT (Topic:{}) - {}".format(topic, payload))
    if topic == ftopic("raw_powerswitch"):
        if payload == "ON" or payload == "1":
            print("Manual power switch ON")
            POWERSWITCH.on()
        elif payload == "OFF" or payload == "0":
            print("Manual power switch OFF")
            POWERSWITCH.off()
    elif topic == ftopic("cmd"):
        if payload == "STOP":
            print("Manual Loop STOP")
            keep_looping = False
        elif payload == "RESET" or payload == "REBOOT":
            print("Manual Reboot")
            reset()


client = MQTTClient(SETTINGS_MQTT["name"], SETTINGS_MQTT["broker"], SETTINGS_MQTT["port"])
client.set_callback(sub_callback)
client.connect()
client.subscribe((TOPIC["base"]+"#").encode())
print("PC Monitor MQTT client connected!")

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
            print("Error on loop:\n{}".format(ex))

loop()

print("PC Monitor script ended!")
