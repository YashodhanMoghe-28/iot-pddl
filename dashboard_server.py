import json
import paho.mqtt.client as mqtt
from flask import Flask, render_template
from flask_socketio import SocketIO

BROKER_IP   = "localhost"
BROKER_PORT = 1883

SENSOR_TOPIC   = "sensors/zone1"
ACTUATOR_TOPIC = "actuators/zone1"
ACTION_TOPIC   = "actions/zone1"
SYSTEM_TOPIC   = "system/zone1"

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

connected_clients = 0

def on_connect(client, userdata, connect_flags, reason_code, properties):
    print("[MQTT] Connected, reason_code =", reason_code)
    client.subscribe(SENSOR_TOPIC)
    client.subscribe(ACTUATOR_TOPIC)
    client.subscribe(ACTION_TOPIC)
    client.subscribe(SYSTEM_TOPIC)
    print("[MQTT] Subscribed to all topics")

def on_message(client, userdata, msg):
    print("[MQTT] Received on:", msg.topic)

    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print("[MQTT] Parse error:", e)
        return

    print("[MQTT] Payload:", payload)

    with app.app_context():
        if msg.topic == SENSOR_TOPIC:
            socketio.emit("sensor_update", payload)
            print("[SocketIO] Emitted sensor_update")
        elif msg.topic == ACTUATOR_TOPIC:
            socketio.emit("actuator_update", payload)
            print("[SocketIO] Emitted actuator_update")
        elif msg.topic == ACTION_TOPIC:
            socketio.emit("action_update", payload)
            print("[SocketIO] Emitted action_update")
        elif msg.topic == SYSTEM_TOPIC:
            socketio.emit("system_update", payload)
            print("[SocketIO] Emitted system_update")

from paho.mqtt.client import CallbackAPIVersion
mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
mqtt_client.loop_start()

@app.route("/")
def index():    
    return render_template("dashboard.html")

@socketio.on("connect")
def handle_connect():
    global connected_clients
    connected_clients += 1
    print("[SocketIO] Client connected. Total:", connected_clients)

@socketio.on("disconnect")
def handle_disconnect():
    global connected_clients
    connected_clients -= 1
    print("[SocketIO] Client disconnected. Total:", connected_clients)

if __name__ == "__main__":
    print("Dashboard running at http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)