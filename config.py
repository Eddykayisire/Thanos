# config.py
import os
import json

# Application data directory
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".thanos")
VAULT_DB_FILE = os.path.join(APP_DATA_DIR, "vault.db")
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")

# --- Security Settings ---
# Incorrect login attempts
MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS = 5
LOGIN_BLOCK_DELAY_SECONDS = 5

# Security Photo Capture
SECURITY_PHOTO_ENABLED = True # Set to True in settings to enable
SECURITY_PHOTO_DIR = os.path.join(APP_DATA_DIR, "security_photos")

# Email Alerts
EMAIL_ALERTS_ENABLED = True # Set to True in settings to enable
EMAIL_SENDER = os.getenv("THANOS_EMAIL_SENDER", "noreply@example.com") # Configure your sender email
EMAIL_RECIPIENT = "" # Configure recipient
SMTP_SERVER = os.getenv("THANOS_SMTP_SERVER", "smtp.example.com") # Configure your SMTP server
SMTP_PORT = 587 # Common SMTP port (587 for TLS, 465 for SSL)
SMTP_USERNAME = os.getenv("THANOS_SMTP_USERNAME", "apikey") # Configure your SMTP username
SMTP_PASSWORD = os.getenv("THANOS_SMTP_PASSWORD", "") # Load from environment variable
# Theme
THEME = 'dark'  # 'dark' or 'light'

# Security photo
SECURITY_PHOTO_ENABLED = True

# Load settings from JSON if exists
def load_settings():
    global MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS, EMAIL_RECIPIENT, EMAIL_SENDER, SMTP_USERNAME, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS = int(data.get("max_attempts", MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS))
                EMAIL_RECIPIENT = data.get("email_recipient", EMAIL_RECIPIENT)
                EMAIL_SENDER = data.get("email_sender", EMAIL_SENDER)
                SMTP_SERVER = data.get("smtp_server", SMTP_SERVER)
                SMTP_PORT = int(data.get("smtp_port", SMTP_PORT))
                SMTP_USERNAME = data.get("smtp_username", SMTP_USERNAME)
                SMTP_PASSWORD = data.get("smtp_password", SMTP_PASSWORD)
                # Optional settings
                try:
                    THEME_VAL = data.get("theme", None)
                    if THEME_VAL in ("dark", "light"):
                        globals()['THEME'] = THEME_VAL
                except Exception:
                    pass
                try:
                    globals()['SECURITY_PHOTO_ENABLED'] = bool(data.get("security_photo_enabled", SECURITY_PHOTO_ENABLED))
                except Exception:
                    pass
                try:
                    globals()['EMAIL_ALERTS_ENABLED'] = bool(data.get("email_alerts_enabled", EMAIL_ALERTS_ENABLED))
                except Exception:
                    pass
        except Exception:
            pass

load_settings()
                                     # In a real app, this should be encrypted or
                                     # prompted securely. For this exercise, it's a placeholder.