import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC = "sensor/motion"

def on_connect(client, userdata, flags, rc):
    print("Connected")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    message = msg.payload.decode()

    if message == "True":
        print("🚨 MOTION DETECTED")

    else:
        print("No Motion")

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)

client.loop_forever()