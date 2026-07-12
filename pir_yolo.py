import cv2
import time
import paho.mqtt.client as mqtt
from ultralytics import YOLO

# ---------------- MQTT SETTINGS ----------------
BROKER = "localhost"
TOPIC = "sensor/motion"

# ---------------- YOLO MODEL ----------------
model = YOLO("yolov8n.pt")

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(0)

# ---------------- MOTION VARIABLES ----------------
motion_detected = False
last_motion_time = 0

# ---------------- MQTT CALLBACKS ----------------
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    global motion_detected
    global last_motion_time

    message = msg.payload.decode()

    if message == "True":

        motion_detected = True

        # update latest motion timestamp
        last_motion_time = time.time()

        print("🚨 MOTION DETECTED")

# ---------------- MQTT CLIENT ----------------
client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)

client.loop_start()

# ---------------- MAIN LOOP ----------------
while True:

    ret, frame = cap.read()

    if not ret:
        break

    # ---------------- STOP YOLO AFTER 2 SEC ----------------
    if motion_detected:

        # if no motion received for 2 sec
        if time.time() - last_motion_time > 2:

            motion_detected = False

            print("⏹ No motion for 2 sec - YOLO stopped")

    # ---------------- RUN YOLO ONLY DURING MOTION ----------------
    if motion_detected:

        results = model(frame)

        for result in results:

            boxes = result.boxes

            for box in boxes:

                cls = int(box.cls[0])

                # person class
                if cls == 0:

                    confidence = float(box.conf[0])

                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    # Draw bounding box
                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    label = f"Person {confidence:.2f}"

                    cv2.putText(
                        frame,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                    print(f"🧍 Person Detected {confidence:.2f}")

    # ---------------- DISPLAY ----------------
    cv2.imshow("PIR + YOLOv8 Surveillance", frame)

    # Quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ---------------- CLEANUP ----------------
cap.release()
cv2.destroyAllWindows()
client.loop_stop()