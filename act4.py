"""
actuator_executor.py

Runs on Raspberry Pi

CHANGES IN THIS VERSION (on top of your working I2C-retry version):

  1. LED FIX
     Previously, activate_noise_warning() / activate_door_alert() /
     deactivate_noise_warning() / deactivate_door_alert() each wrote
     directly to VIOLATION_LED_PORT independently. Since both share the
     same physical LED, clearing ONE violation could wrongly turn the
     LED off while ANOTHER violation was still active.

     Fix: activate/deactivate functions now ONLY update actuator_state
     flags. A single function, update_status_leds(), is called once per
     message and recomputes LED state from the FULL actuator_state:
       - VIOLATION_LED_PORT (5)  -> ON if buzzer_on OR noise_warning_on
                                     OR door_alert_on (i.e. ANY violation)
       - OCCUPANCY_LED_PORT (6)  -> unchanged, still follows occupancy
       - SPARE_LED_PORT (7)      -> ON only when there is NO violation
                                     (the "all okay" indicator you asked for)

  2. LCD DEFAULT-STATE FIX
     Previously, deactivate_*() functions never called setText() at all,
     so the LCD kept showing the last violation message forever.

     Fix: update_lcd_display() is called once per message, and ALWAYS
     writes either the highest-priority active violation message, or a
     default "All Clear" message if nothing is active. Priority order
     (highest first): proximity (buzzer) > door > noise -- adjust the
     ordering in update_lcd_display() if you want a different priority.

  3. NETWORK / STALE-ACTION HANDLING
     Every action message now carries a "timestamp" field set on
     Laptop 1 when it was generated (see updated planning_loop.py).
     If an action arrives here older than MAX_ACTION_AGE_SECONDS, it is
     almost certainly a delayed message from BEFORE a network hiccup --
     it is dropped instead of applied, so a late "sound-buzzer" from a
     violation that has since cleared can't turn the buzzer on after
     the fact.

     An on_disconnect handler also shows "NETWORK ERROR" on the LCD
     immediately when the RPi loses its connection to the broker (this
     needs no network, just local I2C), and update_lcd_display() /
     update_status_leds() are re-run on reconnect so the display goes
     back to reflecting the TRUE current actuator_state once the link
     is back up.

  Nothing about which MQTT action names map to which actuator was
  changed -- turn-on-fan / sound-buzzer / etc. all still do exactly
  what they did before. Only the LED/LCD *display* logic and the
  handling of late-arriving messages were added.
"""

import time
import json
import smbus
import grovepi
import paho.mqtt.client as mqtt
from grove_rgb_lcd import setRGB, setText

# --------------------------------------------------
# MQTT
# --------------------------------------------------

BROKER_IP = "192.168.0.105"
BROKER_PORT = 1883

ACTION_TOPIC = "actions/zone1"
ACTUATOR_TOPIC = "actuators/zone1"
SYSTEM_TOPIC = "system/zone1"    # NEW: for network status / dropped-message notices

# --------------------------------------------------
# Ports
# --------------------------------------------------

VIOLATION_LED_PORT = 5
OCCUPANCY_LED_PORT = 6
SPARE_LED_PORT = 7
BUZZER_PORT = 8

grovepi.pinMode(VIOLATION_LED_PORT, "OUTPUT")
grovepi.pinMode(OCCUPANCY_LED_PORT, "OUTPUT")
grovepi.pinMode(SPARE_LED_PORT, "OUTPUT")
grovepi.pinMode(BUZZER_PORT, "OUTPUT")

# --------------------------------------------------
# Relay Board (unchanged from your working I2C-retry version)
# --------------------------------------------------

DEVICE_ADDRESS = 0x20
DEVICE_REG_MODE1 = 0x06

bus = smbus.SMBus(1)

relay_state = 0xFF
time.sleep(0.2)


def i2c_write_relay(value, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            bus.write_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1, value)
            return True
        except IOError as e:
            print("I2C write failed (attempt {}/{}): {}".format(attempt, max_retries, e))
            time.sleep(0.1 * attempt)
    print("I2C write to relay FAILED after {} attempts.".format(max_retries))
    return False


i2c_write_relay(relay_state)

# --------------------------------------------------
# Actuator State
# --------------------------------------------------

actuator_state = {
    "fan_on": False,
    "buzzer_on": False,
    "occupancy_led_on": False,
    "noise_warning_on": False,
    "door_alert_on": False
}

# --------------------------------------------------
# Network / staleness config
# --------------------------------------------------

MAX_ACTION_AGE_SECONDS = 5.0   # actions older than this are dropped as stale
network_ok = True              # tracks our own connection to the broker


def is_action_stale(timestamp):
    if timestamp is None:
        return False   # no timestamp provided -- treat as fresh (backward compatible)
    age = time.time() - timestamp
    return age > MAX_ACTION_AGE_SECONDS


# --------------------------------------------------
# Fan Relay (unchanged)
# --------------------------------------------------

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


# --------------------------------------------------
# Buzzer (physical actuator -- unchanged mechanism)
# --------------------------------------------------

def set_buzzer(on):
    grovepi.digitalWrite(BUZZER_PORT, 1 if on else 0)
    actuator_state["buzzer_on"] = on


# --------------------------------------------------
# Occupancy LED (unchanged -- this one already worked correctly)
# --------------------------------------------------

def set_occupancy_led(on):
    grovepi.digitalWrite(OCCUPANCY_LED_PORT, 1 if on else 0)
    actuator_state["occupancy_led_on"] = on


# --------------------------------------------------
# Noise / Door -- NOW ONLY UPDATE STATE, no direct hardware writes.
# update_status_leds() / update_lcd_display() handle the hardware.
# --------------------------------------------------

def activate_noise_warning():
    actuator_state["noise_warning_on"] = True


def deactivate_noise_warning():
    actuator_state["noise_warning_on"] = False


def activate_door_alert():
    actuator_state["door_alert_on"] = True


def deactivate_door_alert():
    actuator_state["door_alert_on"] = False


# --------------------------------------------------
# NEW: centralized LED logic
# --------------------------------------------------

def update_status_leds():
    violation = (
        actuator_state["buzzer_on"]
        or actuator_state["noise_warning_on"]
        or actuator_state["door_alert_on"]
    )

    grovepi.digitalWrite(VIOLATION_LED_PORT, 1 if violation else 0)
    grovepi.digitalWrite(SPARE_LED_PORT, 0 if violation else 1)
    # occupancy LED is handled separately by set_occupancy_led(), unchanged


# --------------------------------------------------
# NEW: centralized LCD logic
# Priority when multiple violations are active at once (highest first):
#   proximity (buzzer) > door > noise
# Adjust the order below if you'd prefer a different priority.
# --------------------------------------------------

def update_lcd_display():
    if not network_ok:
        # on_disconnect() already wrote "NETWORK ERROR" -- don't fight it
        return

    if actuator_state["buzzer_on"]:
        setRGB(255, 0, 0)
        setText("VIOLATION\nToo close to machinery")

    elif actuator_state["door_alert_on"]:
        setRGB(255, 0, 0)
        setText("ALERT\nDoor Open")

    elif actuator_state["noise_warning_on"]:
        setRGB(255, 165, 0)
        setText("WARNING\nNoise High")

    else:
        setRGB(0, 255, 0)
        setText("Zone1: All Clear\nFan:{} Occ:{}".format(
            "ON" if actuator_state["fan_on"] else "OFF",
            "Y" if actuator_state["occupancy_led_on"] else "N"
        ))


def refresh_outputs():
    """Call once after any actuator_state change to sync LEDs + LCD."""
    update_status_leds()
    update_lcd_display()


# --------------------------------------------------
# Publish State
# --------------------------------------------------

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


# --------------------------------------------------
# MQTT Callbacks
# --------------------------------------------------

def on_connect(client, userdata, flags, rc):
    global network_ok
    print("Connected")
    client.subscribe(ACTION_TOPIC)

    network_ok = True
    refresh_outputs()   # restore correct LED/LCD state after a reconnect
    publish_system_status("connected")


def on_disconnect(client, userdata, rc):
    global network_ok
    network_ok = False
    print("Disconnected from broker (rc={}). Showing NETWORK ERROR on LCD.".format(rc))

    # This needs no network -- it's a local I2C write, so it works even
    # while we're offline from the broker.
    try:
        setRGB(0, 0, 255)
        setText("NETWORK ERROR\nReconnecting...")
    except Exception as e:
        print("Could not update LCD during disconnect:", e)


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
            return   # do NOT apply this action, do NOT publish_state()

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


# --------------------------------------------------
# MQTT
# --------------------------------------------------

client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.connect(BROKER_IP, BROKER_PORT, 60)

# --------------------------------------------------
# Main
# --------------------------------------------------

print("Actuator Executor Started")

refresh_outputs()  #  show correct "All Clear" state on boot
publish_state()

client.loop_forever()
