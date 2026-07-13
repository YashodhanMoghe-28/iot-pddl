"""
sensor_publisher.py

Raspberry Pi

ONLY RESPONSIBILITIES:

1. Read sensors
2. Determine environmental state
3. Publish MQTT

NO actuator control.
NO fan control.
NO buzzer control.
NO LEDs.
NO LCD.

The planner decides all actions.

CHANGES IN THIS VERSION:

  1. OCCUPANCY_CHECK_INTERVAL changed from 15s to 300s (5 minutes),
     as requested. PIR is checked once every 5 minutes and the result
     is latched until the next check.

  2. Occupancy gating: proximity_violation and noise_high are now
     forced to False whenever the zone is NOT occupied, regardless of
     the raw sensor reading. There is no reason to sound a
     too-close-to-machinery buzzer or a noise warning if nobody is
     actually in the zone. temp_high and door_open are UNCHANGED --
     they stay active regardless of occupancy, since ventilation and
     door security both matter whether or not anyone is present.

     Raw values (proximity_cm, sound_level, etc.) are still read and
     published every cycle exactly as before -- only the DERIVED
     violation flags used by the planner are gated. This keeps the
     dashboard showing live numbers even when occupancy is False.

  This is the PRIMARY gate. domain.pddl also now requires (occupied ?z)
  as an explicit precondition on sound-buzzer / activate-noise-warning,
  as a second, planner-level layer of the same rule.
"""

import time
import math
import json
import grovepi
import paho.mqtt.client as mqtt

# -------------------------------------------------
# MQTT
# -------------------------------------------------

BROKER_IP = "192.168.0.105"   # Windows Laptop
BROKER_PORT = 1883

SENSOR_TOPIC = "sensors/zone1"

# -------------------------------------------------
# Ports
# -------------------------------------------------

TEMP_HUMIDITY_PORT = 4
ULTRASONIC_PORT    = 3
PIR_PORT           = 2

SOUND_PORT = 0      # A0
ANGLE_PORT = 1      # A1

DHT_SENSOR_TYPE = 0

ADC_REF    = 5
GROVE_VCC  = 5
FULL_ANGLE = 300

# -------------------------------------------------
# Thresholds
# -------------------------------------------------

THRESHOLDS = {
    "temperature": 30.0,
    "proximity_cm": 10,
    "sound_level": 270,
    "door_angle": 15
}

# Re-check interval while OCCUPIED (slow poll). While VACANT, checks
# happen every cycle instead (fast poll) -- see update_occupancy() below.
OCCUPANCY_CHECK_INTERVAL = 300

# -------------------------------------------------
# Grove setup
# -------------------------------------------------

grovepi.pinMode(PIR_PORT, "INPUT")
grovepi.pinMode(SOUND_PORT, "INPUT")
grovepi.pinMode(ANGLE_PORT, "INPUT")

# -------------------------------------------------
# MQTT
# -------------------------------------------------

client = mqtt.Client()
client.connect(BROKER_IP, BROKER_PORT, 60)
client.loop_start()

# -------------------------------------------------
# Occupancy Latch
# -------------------------------------------------

occupancy_state = {
    "occupied": False,
    "last_check": 0
}

def update_occupancy():

    now = time.time()

    if occupancy_state["occupied"]:

        # Currently believed OCCUPIED -- slow poll. Only re-check once
        # every OCCUPANCY_CHECK_INTERVAL seconds, since someone already
        # confirmed present is expected to still be there shortly after.
        if now - occupancy_state["last_check"] >= OCCUPANCY_CHECK_INTERVAL:

            try:
                motion = grovepi.digitalRead(PIR_PORT)

                occupancy_state["occupied"] = bool(motion)

            except:
                pass

            occupancy_state["last_check"] = now

    else:

        # Currently believed VACANT -- fast poll. Check every single
        # cycle (same cadence as the main loop, ~1s) so a new entry is
        # detected almost immediately instead of being missed for up
        # to OCCUPANCY_CHECK_INTERVAL seconds, which was the original bug:
        # someone walking in right after a "vacant" reading would have
        # gone undetected for up to 5 minutes.
        try:
            motion = grovepi.digitalRead(PIR_PORT)

            occupancy_state["occupied"] = bool(motion)

        except:
            pass

        occupancy_state["last_check"] = now

    return occupancy_state["occupied"]

# -------------------------------------------------
# Sensor Reads
# -------------------------------------------------

def read_temperature_humidity():

    try:

        temp, hum = grovepi.dht(
            TEMP_HUMIDITY_PORT,
            DHT_SENSOR_TYPE
        )

        if math.isnan(temp) or math.isnan(hum):
            return None, None

        return round(temp,2), round(hum,2)

    except:
        return None, None


def read_ultrasonic():

    try:
        return grovepi.ultrasonicRead(ULTRASONIC_PORT)
    except:
        return None


def read_sound():

    try:
        return grovepi.analogRead(SOUND_PORT)
    except:
        return None


def read_door_angle():

    try:

        value = grovepi.analogRead(ANGLE_PORT)

        voltage = float(value) * ADC_REF / 1023

        angle = (voltage * FULL_ANGLE) / GROVE_VCC

        return round(angle,2)

    except:
        return None

# -------------------------------------------------
# Read All Sensors
# -------------------------------------------------

def read_all_sensors():

    temp, hum = read_temperature_humidity()

    proximity = read_ultrasonic()

    sound = read_sound()

    angle = read_door_angle()

    occupied = update_occupancy()

    return {

        "temperature": temp,
        "humidity": hum,

        "proximity_cm": proximity,

        "sound_level": sound,

        "door_angle": angle,

        "occupied": occupied,

        # NEW: lets the dashboard show a countdown to the next
        # occupancy check. Both values use the RPi's own clock, so the
        # dashboard only needs to trust the DIFFERENCE between them,
        # not the absolute timestamps -- avoids RPi/laptop clock skew.
        "occupancy_last_check": occupancy_state["last_check"],
        "occupancy_check_interval": OCCUPANCY_CHECK_INTERVAL,

        "timestamp": time.time()
    }

# -------------------------------------------------
# Convert to Planning Predicates
#
# CHANGED: proximity_violation and noise_high are now gated behind
# occupancy. temp_high and door_open are unchanged -- always active.
# -------------------------------------------------

def detect_environment_state(state):

    occupied = state["occupied"]

    temp_high = (
        state["temperature"] is not None and
        state["temperature"] > THRESHOLDS["temperature"]
    )

    # Only meaningful if someone is actually in the zone.
    proximity_violation = (
        occupied and
        state["proximity_cm"] is not None and
        state["proximity_cm"] < THRESHOLDS["proximity_cm"]
    )

    # Only meaningful if someone is actually in the zone.
    noise_high = (
        occupied and
        state["sound_level"] is not None and
        state["sound_level"] > THRESHOLDS["sound_level"]
    )

    door_open = (
        state["door_angle"] is not None and
        state["door_angle"] > THRESHOLDS["door_angle"]
    )

    return {
        "temp_high": temp_high,
        "proximity_violation": proximity_violation,
        "noise_high": noise_high,
        "door_open": door_open
    }

# -------------------------------------------------
# Publish
# -------------------------------------------------

def publish_state(state, predicates):

    payload = {}

    payload.update(state)

    payload.update(predicates)

    client.publish(
        SENSOR_TOPIC,
        json.dumps(payload)
    )

    return payload

# -------------------------------------------------
# Main
# -------------------------------------------------

if __name__ == "__main__":

    print("Sensor Publisher Started")
    print("Occupancy checked every {}s (latched between checks)".format(OCCUPANCY_CHECK_INTERVAL))
    print("Proximity/noise violations only count while occupied.")

    try:

        while True:

            state = read_all_sensors()

            predicates = detect_environment_state(state)

            payload = publish_state(
                state,
                predicates
            )

            print(json.dumps(payload))

            time.sleep(1)

    except KeyboardInterrupt:

        print("Stopping")

        client.loop_stop()

        client.disconnect()
