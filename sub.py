import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC = "test/message"

def on_connect(client, userdata, flags, rc):
    print("Connected to broker")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    message = msg.payload.decode()
    print("Received:", message)

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)

print("Waiting for messages...")

client.loop_forever()