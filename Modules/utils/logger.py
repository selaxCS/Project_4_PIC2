import logging
import os
from datetime import datetime

# Route configuration
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Logger Configuration
LOG_FILE = os.path.join(LOG_DIR, "iot_sim.log")

class CustomLogger:
    def __init__(self, name="IoT_System"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Avoid duplicating handlers if called multiple times
        if not self.logger.handlers:
            # Detailed format for file and console
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s : %(message)s',
                datefmt='%H:%M:%S'
            )

            # Console handler (DEBUG and higher)
            console_h = logging.StreamHandler()
            console_h.setLevel(logging.DEBUG)
            console_h.setFormatter(formatter)

            # File handler 
            file_h = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
            file_h.setLevel(logging.DEBUG)
            file_h.setFormatter(formatter)

            self.logger.addHandler(console_h)
            self.logger.addHandler(file_h)

    def get_logger(self):
        return self.logger

# Global instance for the entire application
iot_logger = CustomLogger().get_logger()

def log_startup():
    separator = "=" * 60
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f"\n{separator}\n  NEW IoT SIMULATION SESSION - {timestamp}\n{separator}"
    iot_logger.info(msg)
