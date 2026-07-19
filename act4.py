import time
import json
import smbus
import grovepi
import paho.mqtt.client as mqtt
from grove_rgb_lcd import setRGB, setText

BROKER_IP = "192.168.0.105"
BROKER_PORT = 1883

ACTION_TOPIC = "actions/zone1"
ACTUATOR_TOPIC = "actuators/zone1"
SYSTEM_TOPIC = "system/zone1"

VIOLATION_LED_PORT = 5
OCCUPANCY_LED_PORT = 6
SPARE_LED_PORT = 7
BUZZER_PORT = 8

grovepi.pinMode(VIOLATION_LED_PORT, "OUTPUT")
grovepi.pinMode(OCCUPANCY_LED_PORT, "OUTPUT")
grovepi.pinMode(SPARE_LED_PORT, "OUTPUT")
grovepi.pinMode(BUZZER_PORT, "OUTPUT")

grovepi.digitalWrite(VIOLATION_LED_PORT, 0)
grovepi.digitalWrite(OCCUPANCY_LED_PORT, 0)
grovepi.digitalWrite(SPARE_LED_PORT, 1)
grovepi.digitalWrite(BUZZER_PORT, 0)

def safe_i2c_call(fn, *args, max_retries=5, label="I2C call", **kwargs):
    for attempt in range(1, max_retries + 1):
        try:
            fn(*args, **kwargs)
            return True
        except (IOError, OSError) as e:
            print("{} failed (attempt {}/{}): {}".format(label, attempt, max_retries, e))
            time.sleep(0.08 * attempt)
    print("{} FAILED after {} attempts -- giving up.".format(label, max_retries))
    return False

DEVICE_ADDRESS = 0x20
DEVICE_REG_MODE1 = 0x06

bus = smbus.SMBus(1)

relay_state = 0xFF
time.sleep(0.2)

def i2c_write_relay(value, max_retries=5):
    return safe_i2c_call(
        bus.write_byte_data, DEVICE_ADDRESS, DEVICE_REG_MODE1, value,
        max_retries=max_retries, label="Relay write"
    )

i2c_write_relay(relay_state)

time.sleep(1.0)

actuator_state = {
    "fan_on": False,
    "buzzer_on": False,
    "occupancy_led_on": False,
    "noise_warning_on": False,
    "door_alert_on": False
}

MAX_ACTION_AGE_SECONDS = 5.0
network_ok = True

def is_action_stale(timestamp):
    if timestamp is None:
        return False
    age = time.time() - timestamp
    return age > MAX_ACTION_AGE_SECONDS

def set_fan(on):
    global relay_state

    new_state = (relay_state & ~(1 << 0)) if on else (relay_state | (1 << 0))

    print("Relay write -> target state: {}  byte: {}".format(
        "ON" if on else "OFF", bin(new_state)
    ))

    time.sleep(0.02)
    success = i2c_write_relay(new_state)

    if success:
        relay_state = new_state
        actuator_state["fan_on"] = on
    else:
        print("WARNING: fan_on actuator_state NOT updated -- relay write failed.")

def set_buzzer(on):
    success = safe_i2c_call(
        grovepi.digitalWrite, BUZZER_PORT, 1 if on else 0,
        label="Buzzer write"
    )

    if success:
        actuator_state["buzzer_on"] = on
    else:
        print("WARNING: buzzer_on actuator_state NOT updated -- write failed.")

def set_occupancy_led(on):
    success = safe_i2c_call(
        grovepi.digitalWrite, OCCUPANCY_LED_PORT, 1 if on else 0,
        label="Occupancy LED write"
    )

    if success:
        actuator_state["occupancy_led_on"] = on
    else:
        print("WARNING: occupancy_led_on actuator_state NOT updated -- write failed.")

def activate_noise_warning():
    actuator_state["noise_warning_on"] = True

def deactivate_noise_warning():
    actuator_state["noise_warning_on"] = False

def activate_door_alert():
    actuator_state["door_alert_on"] = True

def deactivate_door_alert():
    actuator_state["door_alert_on"] = False

def update_status_leds():
    violation = (
        actuator_state["buzzer_on"]
        or actuator_state["noise_warning_on"]
        or actuator_state["door_alert_on"]
    )

    safe_i2c_call(
        grovepi.digitalWrite, VIOLATION_LED_PORT, 1 if violation else 0,
        label="Violation LED write"
    )
    safe_i2c_call(
        grovepi.digitalWrite, SPARE_LED_PORT, 0 if violation else 1,
        label="Spare LED write"
    )

def update_lcd_display():
    if not network_ok:
        return

    if actuator_state["buzzer_on"]:
        safe_i2c_call(setRGB, 255, 0, 0, label="LCD color write")
        safe_i2c_call(setText, "VIOLATION\nToo close to machinery", label="LCD text write")

    elif actuator_state["door_alert_on"]:
        safe_i2c_call(setRGB, 255, 0, 0, label="LCD color write")
        safe_i2c_call(setText, "ALERT\nDoor Open", label="LCD text write")

    elif actuator_state["noise_warning_on"]:
        safe_i2c_call(setRGB, 255, 165, 0, label="LCD color write")
        safe_i2c_call(setText, "WARNING\nNoise High", label="LCD text write")

    else:
        safe_i2c_call(setRGB, 0, 255, 0, label="LCD color write")
        safe_i2c_call(setText, "Zone1: All Clear\nFan:{} Occ:{}".format(
            "ON" if actuator_state["fan_on"] else "OFF",
            "Y" if actuator_state["occupancy_led_on"] else "N"
        ), label="LCD text write")

def refresh_outputs():
    """Call once after any actuator_state change to sync LEDs + LCD."""
    update_status_leds()
    time.sleep(0.02)
    update_lcd_display()

def publish_state():
    client.publish(ACTUATOR_TOPIC, json.dumps(actuator_state))

def publish_system_status(status, extra=None):
    payload = {"status": status, "timestamp": time.time()}
    if extra:
        payload.update(extra)
    try:
        client.publish(SYSTEM_TOPIC, json.dumps(payload))
    except Exception as e:
        print("Could not publish system status:", e)

def on_connect(client, userdata, flags, rc):
    global network_ok
    try:
        print("Connected")
        client.subscribe(ACTION_TOPIC)

        network_ok = True
        refresh_outputs()
        publish_system_status("connected")

    except Exception as e:
        print("ERROR in on_connect:", e)

def on_disconnect(client, userdata, rc):
    global network_ok
    try:
        network_ok = False
        print("Disconnected from broker (rc={}). Showing NETWORK ERROR on LCD.".format(rc))

        safe_i2c_call(setRGB, 0, 0, 255, label="LCD color write (disconnect)")
        safe_i2c_call(setText, "NETWORK ERROR\nReconnecting...", label="LCD text write (disconnect)")

    except Exception as e:
        print("ERROR in on_disconnect:", e)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        action = data["action"]
        timestamp = data.get("timestamp")

        if is_action_stale(timestamp):
            age = time.time() - timestamp
            print("Dropping STALE action '{}' (age {:.1f}s > {:.1f}s limit)".format(
                action, age, MAX_ACTION_AGE_SECONDS
            ))
            publish_system_status("stale_action_dropped", {
                "action": action,
                "age_seconds": round(age, 2)
            })
            return

        print("ACTION:", action)

        if action == "turn-on-fan":
            set_fan(True)

        elif action == "turn-off-fan":
            set_fan(False)

        elif action == "sound-buzzer":
            set_buzzer(True)

        elif action == "stop-buzzer":
            set_buzzer(False)

        elif action == "light-occupancy-led":
            set_occupancy_led(True)

        elif action == "unlight-occupancy-led":
            set_occupancy_led(False)

        elif action == "activate-noise-warning":
            activate_noise_warning()

        elif action == "clear-noise-warning":
            deactivate_noise_warning()

        elif action == "activate-door-alert":
            activate_door_alert()

        elif action == "clear-door-alert":
            deactivate_door_alert()

        refresh_outputs()
        publish_state()

    except Exception as e:
        print("ERROR handling action message:", e)

client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.connect(BROKER_IP, BROKER_PORT, 60)

print("Actuator Executor Started")

refresh_outputs()
publish_state()

client.loop_forever()
