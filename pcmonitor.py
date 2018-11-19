import ujson
import sys
from umqtt.simple import MQTTClient
from machine import Pin, reset
from time import sleep, ticks_ms, ticks_diff


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
power_led = None
def power_led_interrupt_callback(pin):
    global power_led
    value = pin.value()
    if value != power_led:
        power_led = value
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
ESP_ONBOARD_LED = Pin(pinout(SETTINGS_PINOUT["ESPOnboardLED"]), Pin.OUT) #Inverted
ESP_ONBOARD_LED.off()

# Pin functions

def powerswitch(pressed):
    if pressed:
        POWER_SWITCH.on()
        # ESP_ONBOARD_LED.off()
        client.publish(
            topic=ftopic("raw_powerswitch_stat").encode(),
            msg="ON".encode(),
            retain=False
        )
    else:
        POWER_SWITCH.off()
        # ESP_ONBOARD_LED.on()
        client.publish(
            topic=ftopic("raw_powerswitch_stat").encode(),
            msg="OFF".encode(),
            retain=False
        )

def press_and_release():
    powerswitch(True)
    sleep(0.5)
    powerswitch(False)

def turn_off_forced():
    if power_led:
        powerswitch(True)
        LIMIT = 10  # Timeout for waiting for PC to shutdown TODO Set in JSON
        WHILE_SLEEP = 0.25
        limit = LIMIT/WHILE_SLEEP  # Max. number of times the loop iterates
        loops = 0
        while power_led:
            sleep(WHILE_SLEEP)
            loops += 1
            if loops > limit:
                print("Forced shutdown could not be performed, computer seems to be still ON")
        powerswitch(False)


# MQTT Disconnect function
def disconnect():
    global client
    client.publish(
        topic=ftopic("stat").encode(),
        msg="OFF".encode(),
        retain=True
    )
    client.publish(
        topic=ftopic("stat").encode(),
        msg="MANUAL DISCONNECT".encode(),
        retain=False
    )
    client.disconnect()
    client = None

# MQTT callback
keep_looping = True
def sub_callback(topic, payload):
    global keep_looping
    topic = topic.decode()
    payload = payload.decode().upper()
    print("Received MQTT (Topic:{}) - {}".format(topic, payload))
    if topic == ftopic("raw_powerswitch_cmd"):  # Commands to directly manipulate the power switch
        if payload == "ON" or payload == "1":
            print("Manual power switch ON")
            powerswitch(True)
        elif payload == "OFF" or payload == "0":
            print("Manual power switch OFF")
            powerswitch(False)
    elif topic == ftopic("cmd_esp"):  # Commands for the ESP
        if payload == "STOP":  # Stop the Loop
            print("Manual Loop STOP")
            keep_looping = False
        elif payload == "RESET" or payload == "REBOOT":  # Reboot the system
            print("Manual Reboot")
            disconnect()
            sleep(3) # Let messages to be sent?
            reset()
    elif topic == ftopic("cmd_pc"):  # Commands for the computer
        if payload == "ON":  # Turn ON or OFF the computer (press and release once the power switch)
            print("Turn {} the computer".format(payload))
            press_and_release()
        elif payload == "FORCE OFF" or payload == "FORCE_OFF":  # Force Turn OFF the computer (by keeping power switch pressed)
            print("Force Turn OFF the computer")
            turn_off_forced()
        elif payload == "SLEEP":  # Sleep (suspend) the computer (via software?)
            pass


client = None

def connect_mqtt():
    global client
    # MQTT startup
    ESP_ONBOARD_LED.off()
    print("Connecting MQTT...")
    client = MQTTClient(
        client_id=SETTINGS_MQTT["name"],
        server=SETTINGS_MQTT["broker"],
        port=SETTINGS_MQTT["port"],
        user=SETTINGS_MQTT["user"] if SETTINGS_MQTT["user"] else None,
        password=SETTINGS_MQTT["password"] if SETTINGS_MQTT["password"] else None,
        keepalive=SETTINGS_MQTT["keepalive"]
    )
    client.set_callback(sub_callback)
    client.set_last_will(
        topic=ftopic("stat").encode(),
        msg="OFF".encode(),
        retain=True
    )
    client.connect()
    # We subscribe to all 'cmd' topics
    client.subscribe(topic=(ftopic("cmd")+"/#").encode())
    client.publish(
        topic=ftopic("stat").encode(),
        msg="ON".encode(),
        retain=True
    )
    print("PC Monitor MQTT client connected!")
    ESP_ONBOARD_LED.on()


# Main Loop
def loop():
    global keep_looping
    keep_looping = True
    last_blink = False
    last_ping = ticks_ms()
    ping_freq = SETTINGS_MQTT["ping_freq"] * 1000

    if client is None:
        connect_mqtt()
    
    print("Loop started")
    while keep_looping:
        try:
            #client.wait_msg()
            client.check_msg()
            current_millis = ticks_ms()
            if ticks_diff(current_millis, last_ping) >= ping_freq:
                client.ping()
                last_ping = current_millis
            sleep(0.075)
        except KeyboardInterrupt:
            break
        except Exception as ex:
            print("Error on loop:")
            sys.print_exception(ex)
            sleep(5)
        else:  # Blink onboard LED
            if last_blink:
                ESP_ONBOARD_LED.on()
            else:
                ESP_ONBOARD_LED.off()
            last_blink = not last_blink
    
    # MQTT Disconnect when loop ends
    disconnect()
