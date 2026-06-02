import paho.mqtt.client as mqtt
import json
import time
import random
import os
import logging
from pathlib import Path

# Logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MULTI_PLC_SIM")

class PLCSimulator:
    def __init__(self, broker_ip="iot_mqtt_broker"):
        self.broker_ip = broker_ip
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    def run(self):
        try:
            self.client.connect(self.broker_ip, 1883, 60)
            logger.info(f"Connected to broker at {self.broker_ip}")
            
            # Load config once or inside loop if you want dynamic updates
            base_path = Path(__file__).resolve().parent.parent.parent
            config_path = base_path / 'IoT_Simulation' / 'config.json'
            
            while True:
                if not os.path.exists(config_path):
                    logger.error("config.json not found!")
                    time.sleep(10)
                    continue

                with open(config_path, 'r') as f:
                    config = json.load(f)

                # Loop through EVERY PLC in the config file
                for plc in config.get('plcs', []):
                    plc_id = str(plc['id'])
                    for sensor in plc.get('sensors', []):
                        s_type = sensor['type']
                        
                        # Generate random value based on type
                        if s_type == "temperature":
                            val = round(random.uniform(18.0, 28.0), 1)
                        elif s_type == "humidity":
                            val = round(random.uniform(40.0, 55.0), 1)
                        else:
                            val = round(random.uniform(0, 100), 2)
                        
                        topic = f"pic2/{plc_id}/{s_type}"
                        self.client.publish(topic, str(val))
                        logger.info(f"Published: {topic} -> {val}")

                time.sleep(5) # Batch update every 5 seconds
                
        except Exception as e:
            logger.error(f"Critical Error: {e}")

if __name__ == "__main__":
    sim = PLCSimulator()
    sim.run()