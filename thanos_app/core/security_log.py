# thanos_app/core/security_log.py
import logging
import os
from config import SECURITY_LOG_FILE

logger = logging.getLogger('ThanosSecurityLogger')
logger.setLevel(logging.INFO)

os.makedirs(os.path.dirname(SECURITY_LOG_FILE), exist_ok=True)

file_handler = logging.FileHandler(SECURITY_LOG_FILE)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)

def log_event(message: str): logger.info(message)
def log_warning(message: str): logger.warning(message)
def log_error(message: str): logger.error(message)
