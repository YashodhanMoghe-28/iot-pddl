<div align="center">

# 🏠 Intelligent IoT Home Automation using AI Planning (PDDL)

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT-green.svg)](https://mqtt.org/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Dashboard-black.svg)](https://flask.palletsprojects.com/)
[![PDDL](https://img.shields.io/badge/AI-PDDL-orange.svg)](https://planning.wiki/)
[![Fast Downward](https://img.shields.io/badge/Planner-Fast%20Downward-red.svg)](https://www.fast-downward.org/)

An intelligent IoT-based home automation system that uses **Artificial Intelligence Planning (PDDL)** to make autonomous decisions based on real-time sensor data instead of traditional rule-based programming.

</div>

---

# 📖 Overview

Traditional IoT systems rely on manually written rules such as:

```python
if temperature > 30:
    turn_on_fan()
```

This project replaces hardcoded decision-making with an **AI Planner**.

The system continuously receives sensor data through MQTT, converts the current environment into a **PDDL Planning Problem**, generates an optimal action plan using the **Fast Downward Planner**, and executes those actions on connected IoT devices.

This approach makes the system:

- Intelligent
- Flexible
- Easy to extend
- Explainable
- Scalable

---

# ✨ Features

- 🌡️ Real-time environmental monitoring
- 🤖 AI Planning using PDDL
- 📡 MQTT communication
- 🧠 Fast Downward planner integration
- 🌐 Live Flask dashboard
- 🚪 Door monitoring
- 🔔 Buzzer alerts
- 💡 Automatic lighting control
- 🌬️ Automatic fan control
- 📊 Live sensor visualization
- ⚡ Reliable MQTT message handling
- 🔄 Automatic action execution

---

# 🏗️ System Architecture

```text
                    +----------------------+
                    |    Sensor Nodes      |
                    | Temperature          |
                    | Humidity             |
                    | Noise                |
                    | Door                 |
                    | Motion               |
                    +----------+-----------+
                               |
                               | MQTT
                               |
                               ▼
                     +-------------------+
                     |    MQTT Broker    |
                     +---------+---------+
                               |
                               ▼
                     +-------------------+
                     |  AI Planner       |
                     |  (planner.py)     |
                     +---------+---------+
                               |
                  Generates PDDL Problem
                               |
                               ▼
                    Fast Downward Planner
                               |
                     Optimal Action Plan
                               |
                               ▼
                     +-------------------+
                     | MQTT Action Topic |
                     +---------+---------+
                               |
                               ▼
                    +----------------------+
                    | Raspberry Pi         |
                    | Actuator Controller  |
                    +---------+------------+
                              |
         +--------------------+--------------------+
         |                    |                    |
       Fan                 Lights              Buzzer

```

---

# 🧠 AI Planning Workflow

```text
Sensor Data
      │
      ▼
Current World State
      │
      ▼
Generate problem.pddl
      │
      ▼
Fast Downward Planner
      │
      ▼
Optimal Plan
      │
      ▼
Execute Actions
      │
      ▼
Update Dashboard
```

---

# 📂 Project Structure

```
iot-pddl/

├── planner.py               # AI planner
├── sensor-pub2.py           # Sensor publisher
├── act4.py                  # Raspberry Pi actuator controller
├── dashboard_server.py      # Flask dashboard
├── dashboard.html           # Dashboard UI
├── domain.pddl              # Planning domain
├── problem.pddl             # Generated planning problem
├── door_alert.mp3           # Alert sound
└── README.md
```

---

# 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| Python | Application development |
| Raspberry Pi | IoT controller |
| GrovePi | Sensor interface |
| MQTT | Communication protocol |
| Paho MQTT | MQTT client |
| Flask | Web dashboard |
| Flask-SocketIO | Live updates |
| HTML/CSS/JavaScript | Dashboard UI |
| PDDL | AI Planning |
| Fast Downward | Automated Planner |

---

# ⚙️ How It Works

1. Sensors continuously collect environmental data.
2. Sensor values are published to the MQTT broker.
3. The planner subscribes to MQTT topics.
4. Current sensor values are converted into a PDDL planning problem.
5. Fast Downward computes the optimal sequence of actions.
6. Planned actions are published through MQTT.
7. Raspberry Pi executes the actions.
8. Dashboard updates in real time.

---

# 🚀 Installation

## Clone the repository

```bash
git clone https://github.com/YashodhanMoghe-28/iot-pddl.git

cd iot-pddl
```

---

## Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## Install MQTT Broker

Example:

```bash
sudo apt install mosquitto
sudo systemctl start mosquitto
```

---

## Start the Dashboard

```bash
python dashboard_server.py
```

---

## Start the Planner

```bash
python planner.py
```

---

## Start the Sensor Publisher

```bash
python sensor-pub2.py
```

---

## Start the Raspberry Pi Controller

```bash
python act4.py
```

---

# 📸 Dashboard

> **Add a screenshot here**

```
images/dashboard.png
```

```markdown
![Dashboard](images/dashboard.png)
```

---

# 📷 Hardware Setup

> Add photos of your hardware here.

```
images/hardware.jpg
```

```markdown
![Hardware](images/hardware.jpg)
```

---

# 🔮 Future Improvements

- Mobile application
- Cloud deployment
- Multiple IoT nodes
- Voice assistant integration
- Predictive automation using Machine Learning
- Docker deployment
- Home Assistant integration

---

# 📚 Learning Outcomes

This project demonstrates knowledge of:

- Artificial Intelligence Planning
- PDDL Modeling
- Automated Planning
- MQTT Communication
- Raspberry Pi Programming
- IoT System Design
- Flask Web Development
- Real-Time Systems
- Distributed Systems
- Python Development

---

# 👨‍💻 Author

**Yashodhan Moghe**

M.Sc. Information Technology  
University of Stuttgart

**Areas of Interest**

- Artificial Intelligence
- Internet of Things (IoT)
- Computer Vision
- Robotics
- Embedded Systems
- Software Engineering

GitHub: https://github.com/YashodhanMoghe-28

---

# ⭐ If you found this project interesting, consider giving it a star!
