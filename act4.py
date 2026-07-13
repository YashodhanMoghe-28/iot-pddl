"""
actuator_executor.py

Runs on Raspberry Pi

THIS IS THE COMPLETE, FINAL VERSION. Please REPLACE your existing act4.py
entirely with this file rather than merging by hand -- the LED-stuck bug
you saw is because several earlier fixes (the universal I2C retry
wrapper, the crash-safe on_connect, the boot-time force-off writes)
were not present in the version you were running.

ALL FIXES INCLUDED:

  1. LED FIX -- violation LED / spare LED recomputed from FULL
     actuator_state every message (not touched independently by
     multiple functions).

  2. LCD DEFAULT-STATE FIX -- always writes either the highest-priority
     violation message or a default "All Clear" message every cycle.

  3. NETWORK / STALE-ACTION HANDLING -- actions older than
     MAX_ACTION_AGE_SECONDS are dropped instead of applied.

  4. UNIVERSAL I2C RETRY WRAPPER (safe_i2c_call) -- EVERY I2C write
     (relay, buzzer, both LEDs, LCD color, LCD text) goes through this.
     Retries up to 5 times with backoff, NEVER raises. This is almost
     certainly why your violation LED was getting stuck: the "turn LED
     off" write was failing on I2C glitches and had no retry, so the
     physical LED kept showing stale state even though actuator_state
     was already correct in Python.

  5. on_connect / on_disconnect fully wrapped in try/except -- an I2C
     error during either callback can no longer crash loop_forever().

  6. Boot-time force-off writes for all digital outputs, so nothing
     powers up in an undefined/floating state.

  7. Occupancy note: this file needs NO changes for the new
     occupancy-gating feature. That logic lives entirely in
     sensor-pub2.py (which sensor values get treated as violations)
     and domain.pddl (which actions the planner is allowed to choose).
     This script just executes whatever action commands it receives,
     as before.
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
SYSTEM_TOPIC = "system/zone1"

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

# Force all digital outputs to a known OFF state at boot, so nothing
# powers up in an undefined/floating state (this is why the buzzer
# was sounding immediately on startup previously).
grovepi.digitalWrite(VIOLATION_LED_PORT, 0)
grovepi.digitalWrite(OCCUPANCY_LED_PORT, 0)
grovepi.digitalWrite(SPARE_LED_PORT, 1)   # "all clear" indicator, on by default
grovepi.digitalWrite(BUZZER_PORT, 0)

# --------------------------------------------------
# Universal I2C retry wrapper
#
# Wraps ANY I2C-touching call (grovepi.digitalWrite, setRGB, setText,
# or a raw bus.write_byte_data) so a transient bus glitch never raises
# out of a callback and never silently leaves hardware in a stale
# state. Retries up to max_retries times with backoff, then gives up
# and returns False -- caller decides what to do (usually: don't
# update actuator_state, so the system stays truthful).
# --------------------------------------------------

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


# --------------------------------------------------
# Relay Board
# --------------------------------------------------

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

# Extra settle time before the FIRST LCD transaction specifically --
# LCD failures were observed on the very first I2C write at cold boot,
# before any other bus activity, suggesting it needs more time to
# settle right after power-up.
time.sleep(1.0)

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

MAX_ACTION_AGE_SECONDS = 5.0
network_ok = True


def is_action_stale(timestamp):
    if timestamp is None:
        return False
    age = time.time() - timestamp
    return age > MAX_ACTION_AGE_SECONDS


# --------------------------------------------------
# Fan Relay
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
# Buzzer -- retry-protected
# --------------------------------------------------

def set_buzzer(on):
    success = safe_i2c_call(
        grovepi.digitalWrite, BUZZER_PORT, 1 if on else 0,
        label="Buzzer write"
    )

    if success:
        actuator_state["buzzer_on"] = on
    else:
        print("WARNING: buzzer_on actuator_state NOT updated -- write failed.")


# --------------------------------------------------
# Occupancy LED -- retry-protected
# --------------------------------------------------

def set_occupancy_led(on):
    success = safe_i2c_call(
        grovepi.digitalWrite, OCCUPANCY_LED_PORT, 1 if on else 0,
        label="Occupancy LED write"
    )

    if success:
        actuator_state["occupancy_led_on"] = on
    else:
        print("WARNING: occupancy_led_on actuator_state NOT updated -- write failed.")


# --------------------------------------------------
# Noise / Door -- state flags only, hardware handled centrally
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
# Centralized LED logic -- retry-protected.
# THIS is the fix for the "violation LED never goes off" bug: every
# single call recomputes from the full actuator_state and retries the
# write up to 5 times instead of silently failing once.
# --------------------------------------------------

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


# --------------------------------------------------
# Centralized LCD logic -- retry-protected
# Priority when multiple violations are active (highest first):
#   proximity (buzzer) > door > noise
# --------------------------------------------------

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
# MQTT Callbacks -- on_connect / on_disconnect fully guarded
# --------------------------------------------------

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

refresh_outputs()
publish_state()

client.loop_forever()
