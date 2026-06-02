# IoT Monitoring Platform with Telegram & Streamlit Dashboard

**Subject:** Programming and Communications 2
**Degree:** Electronic Engineering
**Students:** ALEXANDRU ANTON CATRINOI SFARGHIE 

## 1. Introduction
This project implements a fully integrated, containerized  IoT platform. It expands previous architectures by adding a multi-device simulation environment (`plc_simulator.py`) and an advanced visualization layer (`app.py`) built with Streamlit. The system ingests, processes, stores, and presents real-time telemetry from both physical hardware (ESP8266) and virtual industrial nodes.

The infrastructure is fully orchestrated using Docker Compose to ensure isolation, scalability, and easy deployment.

---

## 2. System Architecture
The platform is organized into five decoupled logical layers:
* **Generation & Simulation Layer:** Physical ESP8266 node (DHT11 sensor) and a local Python multi-device simulator publishing JSON-configured telemetry.
* **Communication Layer:** Eclipse Mosquitto MQTT broker routing messages via the Pub/Sub model under `pic2/#`.
* **Management Layer:** Core Python backend (`main.py`) subscribing to MQTT topics and saving structured data securely into PostgreSQL.
* **Interface Layer:** Asynchronous Telegram bot (`TelegramBot.py`) handling alerts, data subscriptions, and timeout routines.
* **Visualization Layer:** Web dashboard (`app.py`) providing real-time data inspection, historical tables, and interactive threshold charts.

---

## 3. Streamlit Dashboard

### 3.1 Device Selection
Users can select any available device detected in the database. The system automatically determines whether the device is online or offline based on the last received message.

**Status indicators:**
* 🟢 **Online**
* 🔴 **Offline** *(A device is considered offline if no data has been received for more than 20 seconds)*

### 3.2 View Selection
Two visualization modes are available:

#### Graph Mode
Displays sensor values as time series.
* Individual chart per sensor.
* Configurable threshold line.
* Alert message when threshold is exceeded.
* Automatic refresh every 5 seconds.

#### Table Mode
Displays historical records stored in PostgreSQL. Each sensor is shown in a separate table including:
* Timestamp
* Measured value
* Unit

### 3.3 Time Filters
The dashboard allows users to select the period to visualize. Available filters:
* Last N minutes
* Last N hours
* Custom date range
* Last 100 records

This makes it possible to analyse both recent and historical data.

### 3.4 Automatic Refresh
The dashboard includes an **Auto-Refresh** option. When enabled, the page automatically updates every 5 seconds, allowing near real-time monitoring without manually reloading the browser. Users can also manually refresh the page at any time.


---

## 4. Telegram Bot Functionality

| Command | Description | Input Format / Example |
| :--- | :--- | :--- |
| `/start` | Validates admin permissions and prints instructions. | N/A |
| `/set_group` | Registers current chat window for automated notifications. | N/A |
| `/subscribe` | Enables recurring high-frequency telemetry alerts every 15s. | `{"1":["temperature"]}` |
| `/get_data` | Runs an instant query against database states for latest records. | `{"1":["temperature", "humidity"]}` |
| `/create_alert` | Provisions background monitoring limits for active tracking. | `{"1":{"temperature":30.0}}` |

*Note: Dispatching `{}` to `/subscribe` or `/create_alert` clears active triggers.*

Real hardware devices are identified as published in the Arduino code's MQTT file (PIC2_4.ino) 
*(Note: the name cannot contain special characters; the TelegramBot.py code is not prepared to accept these formats).* 
Simulated devices are identified as specified in the config.json file, which uses the format id (1, 2, 3, 4...).

---

## 5. Data Flow and Concurrency
To ensure a non-blocking operational cycle, tasks are isolated across three distinct contexts:
1. **MQTT Thread:** Runs autonomously via `client.loop_start()` to handle incoming data ingestion without locking the database connection.
2. **Asynchronous Loop:** Driven by `asyncio` within the Telegram bot framework to process periodic 15-second tracking and network drop checks.
3. **Reactive Frontend:** Streamlit uses an automated redraw routine calling `st.rerun()` every 5 seconds to query the database and update charts in real time.

---

## 6. Guide

### Step 1: Environment Variables (`.env`)
Place a `.env` file in the root path with your specific configuration keys:
```ini
MQTT_BROKER_IP=iot_mqtt_broker
MQTT_PORT=1883
MQTT_TOPIC_SUB=pic2/#
DB_HOST=iot_database
DB_NAME=iot_db
DB_USER=iot_user
DB_PASSWORD=SecurePassword123
TELEGRAM_TOKEN=1234567890:ABCdefGhIJKlmNoPQRstUVwxyZ_your_token
ADMIN_ID=987654321
```

### Step 2: Flash ESP8266 Hardware Node

Configure the network credentials (`ssid` / `password`) and set `mqtt_broker_ip` to the IPv4 address of your host computer in `PIC2_3_.ino`.
Compile and flash the firmware using the Arduino IDE.

## Step 3: Launch Containers

Build the services and start the background orchestration ecosystem by running this command in the project's root directory:
```bash
docker-compose --env-file .env -f Docker/docker-compose.yml up -d --build
```
Once the containers are running, open your browser and access the iot_dashboard. If other URLs or external commands are required, they can be found in the iot_dashboard container:
```text
```http://localhost:8501
```
to access the real-time dashboard.

