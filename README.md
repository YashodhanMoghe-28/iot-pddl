# IoT-PDDL

AI-planned IoT monitoring and automation. Instead of hardcoded `if temperature > 30: turn_on_fan()` rules, this system models the environment as a PDDL planning problem and lets the [Fast Downward](https://www.fast-downward.org/) planner decide which actions to take.

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT-green.svg)](https://mqtt.org/)
[![Flask](https://img.shields.io/badge/Flask-Dashboard-black.svg)](https://flask.palletsprojects.com/)
[![PDDL](https://img.shields.io/badge/AI-PDDL-orange.svg)](https://planning.wiki/)

## How it works

1. **`sensor-pub2.py`** (runs on the Raspberry Pi) reads temperature/humidity, proximity, sound, door angle, and PIR motion via GrovePi, derives violation flags, and publishes everything to MQTT.
2. **`planner.py`** subscribes to sensor data, writes the current state to `problem.pddl`, runs it against `domain.pddl` with Fast Downward, and publishes the resulting action plan.
3. **`act4.py`** (runs on the Raspberry Pi) subscribes to the action topic and drives the physical outputs: fan relay, buzzer, status LEDs, and an RGB LCD.
4. **`dashboard_server.py`** serves a live Flask + Socket.IO dashboard showing sensor readings, actuator states, and the current plan.

```
Sensors --MQTT--> Planner --PDDL/Fast Downward--> Plan --MQTT--> Actuators
                      |                                             |
                      +-------------------> Dashboard <-------------+
```

## Monitored zone

| Sensor | Reads | Triggers |
|---|---|---|
| Temperature & humidity | °C / % | `temp-high` above threshold |
| Ultrasonic proximity | cm | `proximity-violation` below threshold |
| Sound level | raw | `noise-high` above threshold |
| Door angle | ° | `door-open` above threshold |
| PIR motion | on/off | `occupied`, checked every 5 min and latched |

Proximity and noise violations only count while the zone is `occupied` — occupancy gating is enforced both when sensor values are published and as a precondition in `domain.pddl`.

## Planner actions

`turn-on-fan` / `turn-off-fan` · `sound-buzzer` / `stop-buzzer` · `light-occupancy-led` / `unlight-occupancy-led` · `activate-noise-warning` / `clear-noise-warning` · `activate-door-alert` / `clear-door-alert`

## Project structure

```
iot-pddl/
├── planner.py             # Builds problem.pddl, runs Fast Downward, publishes the plan
├── sensor-pub2.py          # Reads sensors on the Pi, publishes to MQTT
├── act4.py                 # Drives actuators on the Pi
├── dashboard_server.py     # Flask + Socket.IO dashboard backend
├── templates/
│   └── dashboard.html      # Dashboard UI
├── domain.pddl             # Planning domain (predicates + actions)
├── problem.pddl            # Generated planning problem (overwritten each cycle)
├── domain_old.pddl         # Previous domain version, kept for reference
└── door_alert.mp3          # Door-alert sound played by the planner
```

## Tech stack

| Layer | Tools |
|---|---|
| Sensing / actuation | Raspberry Pi, GrovePi, I2C relay + RGB LCD |
| Messaging | MQTT (Mosquitto broker, Paho MQTT client) |
| Planning | PDDL, Fast Downward (`astar(blind())`) |
| Dashboard | Flask, Flask-SocketIO, HTML/CSS/JS |

## Getting started

**Prerequisites**
- Python 3.x
- An MQTT broker (e.g. Mosquitto)
- [Fast Downward](https://www.fast-downward.org/) installed — `planner.py` currently invokes it through WSL (`wsl bash -c "python3 /home/.../fast-downward.py ..."`), so update `FAST_DOWNWARD` and `win_to_wsl()` in `planner.py` to match your setup if you're not on Windows/WSL
- GrovePi hardware, only required to run `sensor-pub2.py` and `act4.py` on the Raspberry Pi itself

**Install dependencies**

```bash
pip install paho-mqtt flask flask-socketio playsound3
# on the Raspberry Pi only:
pip install grovepi smbus
```

**Run**

```bash
# MQTT broker
sudo apt install mosquitto && sudo systemctl start mosquitto

# Dashboard
python dashboard_server.py

# Planner
python planner.py

# On the Raspberry Pi
python sensor-pub2.py
python act4.py
```

Open `http://localhost:5000` (or your dashboard host) to watch it run.

## MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `sensors/zone1` | sensor publisher → planner, dashboard | raw readings + derived violation flags |
| `actions/zone1` | planner → Pi controller | planned action list |
| `actuators/zone1` | Pi controller → dashboard | current actuator states |
| `system/zone1` | various | connection status, stale-action notices |

## Reliability notes

- All I2C writes on the Pi go through a retry wrapper (`safe_i2c_call`) rather than failing silently.
- Actions older than `MAX_ACTION_AGE_SECONDS` are dropped instead of applied, so a network hiccup can't replay a stale command.
- Status LEDs and the LCD are recomputed from the full actuator state on every update, not toggled independently.

## Roadmap

- Mobile app
- Cloud deployment / multi-node support
- Predictive automation with ML
- Docker packaging
- Home Assistant integration

## Author

**Yashodhan Moghe**
M.Sc. Information Technology, University of Stuttgart
[GitHub](https://github.com/YashodhanMoghe-28)
