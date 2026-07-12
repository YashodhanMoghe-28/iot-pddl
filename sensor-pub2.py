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

OCCUPANCY_CHECK_INTERVAL = 15

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

    if now - occupancy_state["last_check"] >= OCCUPANCY_CHECK_INTERVAL:

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

        "timestamp": time.time()
    }

# -------------------------------------------------
# Convert to Planning Predicates
# -------------------------------------------------

def detect_environment_state(state):

    return {

        "temp_high":
            state["temperature"] is not None and
            state["temperature"] > THRESHOLDS["temperature"],

        "proximity_violation":
            state["proximity_cm"] is not None and
            state["proximity_cm"] < THRESHOLDS["proximity_cm"],

        "noise_high":
            state["sound_level"] is not None and
            state["sound_level"] > THRESHOLDS["sound_level"],

        "door_open":
            state["door_angle"] is not None and
            state["door_angle"] > THRESHOLDS["door_angle"]
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
