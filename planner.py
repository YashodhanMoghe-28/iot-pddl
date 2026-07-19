import os
import json
import time
import subprocess
import threading

import paho.mqtt.client as mqtt
from playsound3 import playsound

BROKER_IP = "localhost"
BROKER_PORT = 1883

SENSOR_TOPIC = "sensors/zone1"
ACTUATOR_TOPIC = "actuators/zone1"
ACTION_TOPIC = "actions/zone1"
SYSTEM_TOPIC = "system/zone1"

FAST_DOWNWARD = "/home/yashodhan/fast-downward/fast-downward.py"

DOMAIN_FILE = "domain.pddl"
PROBLEM_FILE = "problem.pddl"

MAX_PUBLISH_RETRIES = 3
PUBLISH_CONFIRM_TIMEOUT = 2

sensor_state = {}

actuator_state = {
    "fan_on": False,
    "buzzer_on": False,
    "occupancy_led_on": False,
    "noise_warning_on": False,
    "door_alert_on": False
}

last_plan = []

door_alert_playing = False

planning_lock = threading.Lock()

def play_door_alert():

    global door_alert_playing

    if door_alert_playing:
        return

    door_alert_playing = True

    def worker():

        global door_alert_playing

        try:
            playsound("door_alert.mp3")
        except Exception as e:
            print("Audio error:", e)

        door_alert_playing = False

    threading.Thread(
        target=worker,
        daemon=True
    ).start()

client = mqtt.Client()

def publish_action_reliable(action):
    payload = json.dumps({
        "action": action,
        "timestamp": time.time()
    })

    for attempt in range(1, MAX_PUBLISH_RETRIES + 1):
        try:
            info = client.publish(ACTION_TOPIC, payload, qos=1)
            info.wait_for_publish(timeout=PUBLISH_CONFIRM_TIMEOUT)

            if info.is_published():
                return True

            print("Publish attempt {}/{} not confirmed for action: {}".format(
                attempt, MAX_PUBLISH_RETRIES, action
            ))

        except Exception as e:
            print("Publish attempt {}/{} raised error for action {}: {}".format(
                attempt, MAX_PUBLISH_RETRIES, action, e
            ))

        time.sleep(0.3)

    print("NETWORK ERROR: failed to deliver action '{}' after {} attempts".format(
        action, MAX_PUBLISH_RETRIES
    ))

    try:
        client.publish(SYSTEM_TOPIC, json.dumps({
            "status": "network_error",
            "action": action,
            "timestamp": time.time()
        }), qos=0)
    except Exception:
        pass

    return False

def desired_actuator_state(s_state):

    goal = []

    if s_state.get("temp_high"):
        goal.append("(fan-on zone1)")
    else:
        goal.append("(not (fan-on zone1))")

    if s_state.get("proximity_violation"):
        goal.append("(buzzer-on zone1)")
    else:
        goal.append("(not (buzzer-on zone1))")

    if s_state.get("occupied"):
        goal.append("(occupancy-led-on zone1)")
    else:
        goal.append("(not (occupancy-led-on zone1))")

    if s_state.get("noise_high"):
        goal.append("(noise-warning-on zone1)")
    else:
        goal.append("(not (noise-warning-on zone1))")

    if s_state.get("door_open"):
        goal.append("(door-alert-on zone1)")
    else:
        goal.append("(not (door-alert-on zone1))")

    return goal

def generate_problem(s_state, a_state):

    init = []

    if s_state.get("temp_high"):
        init.append("(temp-high zone1)")

    if s_state.get("proximity_violation"):
        init.append("(proximity-violation zone1)")

    if s_state.get("noise_high"):
        init.append("(noise-high zone1)")

    if s_state.get("door_open"):
        init.append("(door-open zone1)")

    if s_state.get("occupied"):
        init.append("(occupied zone1)")

    if a_state["fan_on"]:
        init.append("(fan-on zone1)")

    if a_state["buzzer_on"]:
        init.append("(buzzer-on zone1)")

    if a_state["occupancy_led_on"]:
        init.append("(occupancy-led-on zone1)")

    if a_state["noise_warning_on"]:
        init.append("(noise-warning-on zone1)")

    if a_state["door_alert_on"]:
        init.append("(door-alert-on zone1)")

    goal = desired_actuator_state(s_state)

    problem = f"""
(define (problem industrial-instance)

 (:domain industrial-monitor)

 (:objects
    zone1 - zone
 )

 (:init
    {' '.join(init)}
 )

 (:goal
    (and
        {' '.join(goal)}
    )
 )

)
"""

    with open(PROBLEM_FILE, "w") as f:
        f.write(problem)

def win_to_wsl(path):

    path = os.path.abspath(path)

    drive = path[0].lower()

    rest = path[2:].replace("\\", "/")

    return f"/mnt/{drive}{rest}"

def run_planner():

    domain_wsl = win_to_wsl(DOMAIN_FILE)
    problem_wsl = win_to_wsl(PROBLEM_FILE)

    search_expr = "astar(blind())"

    bash_cmd = (
        f'python3 /home/yashodhan/fast-downward/fast-downward.py '
        f'"{domain_wsl}" "{problem_wsl}" '
        f'--search "{search_expr}"'
    )

    cmd = ["wsl", "bash", "-c", bash_cmd]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=False
    )

    if result.returncode != 0:
        print(result.stderr)
        return []

    return parse_plan()

def parse_plan():

    if not os.path.exists("sas_plan"):
        return []

    actions = []

    with open("sas_plan") as f:

        for line in f:

            line = line.strip()

            if not line.startswith("("):
                continue

            action = line[1:].split()[0]

            actions.append(action)

    return actions

def execute_plan(actions):

    global last_plan

    if actions == last_plan:
        return

    last_plan = actions

    print("\nPLAN FOUND")

    for a in actions:

        print(" ->", a)

        success = publish_action_reliable(a)

        if not success:
            print("  (delivery failed -- next planning cycle will re-derive and retry this)")

        time.sleep(0.2)

def planning_cycle():

    if not sensor_state:
        return

    s_snapshot = dict(sensor_state)
    a_snapshot = dict(actuator_state)

    def run():

        with planning_lock:

            generate_problem(s_snapshot, a_snapshot)

            plan = run_planner()

            execute_plan(plan)

    threading.Thread(target=run, daemon=True).start()

def on_connect(client, userdata, flags, rc):

    print("Connected")

    client.subscribe(SENSOR_TOPIC)
    client.subscribe(ACTUATOR_TOPIC)

def on_message(client, userdata, msg):

    global sensor_state
    global actuator_state

    try:
        data = json.loads(msg.payload.decode())
    except:
        return

    if msg.topic == SENSOR_TOPIC:

        sensor_state = data

        print("\nSensor Update")
        print(sensor_state)

        if sensor_state.get("door_open"):
            play_door_alert()

        planning_cycle()

    elif msg.topic == ACTUATOR_TOPIC:

        actuator_state = data

client.on_connect = on_connect
client.on_message = on_message

client.connect(
    BROKER_IP,
    BROKER_PORT,
    60
)

print("Planning Server Started")

client.loop_forever()