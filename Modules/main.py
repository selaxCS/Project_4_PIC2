import os
import time
import datetime
import asyncio
import threading
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

from Modules.utils.logger import iot_logger, log_startup
from Modules.models.TelegramBot import TelegramBot

import paho.mqtt.client as mqtt


env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

MQTT_BROKER_IP = os.getenv("MQTT_BROKER_IP")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "pic2/#") 

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "iot_database"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                connect_timeout=5
            )
            self.create_table()
            iot_logger.info("PostgreSQL connection successfully established.")
        except Exception as e:
            self.conn = None
            iot_logger.error(f"Database is not available yet: {e}. Will retry on the next data point.")

    def create_table(self):
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_data (
                        id SERIAL PRIMARY KEY,
                        plc_id VARCHAR(50),
                        sensor VARCHAR(50),
                        value FLOAT,
                        unit VARCHAR(10),
                        timestamp TIMESTAMP
                    );
                """)
                self.conn.commit()
        except Exception as e:
            if self.conn: self.conn.rollback()
            iot_logger.error(f"Error creating table: {e}")

    def save_data(self, plc_id, sensor_type, value, unit, timestamp):
        # If there is no connection, try to reconnect before saving
        if not self.conn or self.conn.closed != 0:
            self.connect()
        
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    query = "INSERT INTO sensor_data (plc_id, sensor, value, unit, timestamp) VALUES (%s, %s, %s, %s, %s)"
                    cur.execute(query, (plc_id, sensor_type, value, unit, timestamp))
                    self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                iot_logger.error(f"Error saving data: {e}")

    def get_latest_data(self, query_config):
        results = {}
        with self.lock:
            if not self.conn or self.conn.closed != 0:
                self.connect()
            if not self.conn: return results
            
            try:
                with self.conn.cursor() as cur:
                    for plc_id, sensors in query_config.items():
                        results[plc_id] = {}
                        for sensor in sensors:
                            cur.execute(
                                "SELECT value, unit, timestamp FROM sensor_data WHERE plc_id=%s AND sensor=%s ORDER BY timestamp DESC LIMIT 1",
                                (str(plc_id), str(sensor))
                            )
                            row = cur.fetchone()
                            if row:
                                results[plc_id][sensor] = {
                                    "value": float(row[0]), 
                                    "unit": row[1],
                                    "last_update": str(row[2]) 
                                }
                    self.conn.commit() 
            except Exception as e:
                self.conn.rollback() 
                iot_logger.error(f"Error querying the DB for the bot: {e}")
            return results

def _main_mqtt_on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        iot_logger.info(f"Connected to MQTT Broker: {MQTT_BROKER_IP}")
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        iot_logger.error(f"MQTT connection error: {rc}")

def _main_mqtt_on_message(client, userdata, msg):
    try:
        # Get userdata instances (as configured in the Client)
        db = userdata.get('db')
        bot = userdata.get('bot')
        
        if not db:
            iot_logger.error("DatabaseManager not found in userdata")
            return

        payload = msg.payload.decode()
        topic_str = str(msg.topic)

        if "error" in topic_str:
            if bot and bot.group_id and bot.loop:
                alert_message = f"⚠️ *SENSOR ALERT* ⚠️\n{payload}"
                
                asyncio.run_coroutine_threadsafe(
                    bot.app.bot.send_message(chat_id=bot.group_id, text=alert_message, parse_mode="Markdown"),
                    bot.loop
                )
            return
        
        parts = topic_str.split('/')

        if len(parts) >= 3:
            plc_id = parts[1]      # Extract the real ID from the topic
            reading_name = parts[2] # Extract the sensor name
        else:
            # Fallback if the topic does not have the correct format
            plc_id = "Unknown"
            reading_name = parts[-1]

        unit = "C" if "temperature" in reading_name else "%"
        current_timestamp = datetime.datetime.now()
        
        # Save with the specific ID so they don't get mixed up in the DB
        db.save_data(plc_id, reading_name, float(payload), unit, current_timestamp)
        
    except Exception as e:
        iot_logger.error(f"Error processing MQTT message: {e}")

def main():
    log_startup()
    iot_logger.info("Starting IoT Integration Server...")

    db_manager = DatabaseManager()
    bot = TelegramBot(server_instance=db_manager) 
    
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, 
                              userdata={'bot': bot, 'db': db_manager})
    mqtt_client.on_connect = _main_mqtt_on_connect
    mqtt_client.on_message = _main_mqtt_on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
        mqtt_client.loop_start() 
        iot_logger.info("MQTT client connected in the background.")
    except Exception as e:
        iot_logger.error(f"MQTT error: {e}")

    try:
        bot.run() 
    except (KeyboardInterrupt, SystemExit):
        iot_logger.info("Stopping system...")
    finally:
        mqtt_client.loop_stop()

if __name__ == "__main__":
    main()

#docker-compose --env-file .env -f Docker/docker-compose.yml up -d --build