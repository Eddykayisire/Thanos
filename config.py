import os
import json

# --- Chemins de l'application ---
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".thanos")
VAULT_DB_FILE = os.path.join(APP_DATA_DIR, "vault.db")
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")

# --- Paramètres de Sécurité ---
MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS = 5
LOGIN_BLOCK_DELAY_SECONDS = 5

# --- Capture Photo ---
SECURITY_PHOTO_ENABLED = True
SECURITY_PHOTO_DIR = os.path.join(APP_DATA_DIR, "security_photos")

# --- Alertes Email ---
EMAIL_ALERTS_ENABLED = True
EMAIL_SENDER = os.getenv("THANOS_EMAIL_SENDER", "noreply@example.com")
EMAIL_RECIPIENT = ""
SMTP_SERVER = os.getenv("THANOS_SMTP_SERVER", "smtp.example.com")
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("THANOS_SMTP_USERNAME", "apikey")
SMTP_PASSWORD = os.getenv("THANOS_SMTP_PASSWORD", "")

# --- Apparence ---
THEME = 'dark'

def load_settings():
    """Charge la configuration utilisateur depuis le fichier JSON si existant."""
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