"""
subscriber.py
---------------
Runs on the Windows laptop.
Connects to the local Mosquitto broker and receives sensor data
published by the Raspberry Pi.

Before running:
  pip install paho-mqtt

Make sure Mosquitto is running on this machine (port 1883).
"""

import json
import paho.mqtt.client as mqtt

BROKER_IP = "localhost"     # broker is running on this same machine
BROKER_PORT = 1883
SENSOR_TOPIC = "sensors/zone1"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker successfully.")
        client.subscribe(SENSOR_TOPIC)
        print("Subscribed to topic '{}'\n".format(SENSOR_TOPIC))
    else:
        print("Connection failed with code", rc)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print("Received non-JSON message:", msg.payload)
        return

    print("--- Sensor update ---")
    print("  Temperature   : {} C".format(data.get("temperature")))
    print("  Humidity      : {} %".format(data.get("humidity")))
    print("  Proximity     : {} cm".format(data.get("proximity_cm")))
    print("  Occupied      : {}".format(data.get("occupied")))
    print("  Sound level   : {}".format(data.get("sound_level")))
    print("  Door angle    : {} deg".format(data.get("door_angle")))
    print("  Violations    : proximity={} noise={} door={}".format(
        data.get("proximity_violation"),
        data.get("noise_high"),
        data.get("door_open"),
    ))
    print()


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Connecting to broker at {}:{}...".format(BROKER_IP, BROKER_PORT))
client.connect(BROKER_IP, BROKER_PORT, keepalive=60)

print("Listening for messages. Press Ctrl+C to stop.\n")
client.loop_forever()