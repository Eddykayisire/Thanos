# thanos_app/core/security_manager.py
import os
import datetime
import json
import smtplib
import io
from email.mime.text import MIMEText
from typing import Dict, Any

try:
    import cv2
    _CAMERA_AVAILABLE = True
except ImportError:
    _CAMERA_AVAILABLE = False
    print("Warning: 'opencv-python' not found. Security camera capture will be disabled.")

from thanos_app.core.crypto import encrypt_data, decrypt_data, encrypt_binary, decrypt_binary
from thanos_app.core.database import DatabaseManager
from thanos_app.core.definitions import (
    LOG_EVENT_INCORRECT_ATTEMPT, LOG_EVENT_SECURITY_TRIGGER,
    LOG_EVENT_PHOTO_CAPTURE, LOG_EVENT_EMAIL_ALERT
)
from thanos_app.core.device_binding import get_device_id
import config

class SecurityManager:
    def __init__(self, db_manager: DatabaseManager, vault_key: bytes):
        self.db = db_manager
        self.vault_key = vault_key
        os.makedirs(config.SECURITY_PHOTO_DIR, exist_ok=True)
        self.db.create_logs_table() # Ensure logs table exists

    def is_camera_available(self) -> bool:
        return _CAMERA_AVAILABLE

    def _encrypt_log_entry(self, log_data: Dict[str, Any]) -> bytes:
        """Encrypts a log entry dictionary into bytes."""
        json_data = json.dumps(log_data)
        return encrypt_data(self.vault_key, json_data)

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """
        Logs a security event to the encrypted local journal.
        Details should not contain sensitive information in plaintext.
        """
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        encrypted_data = self._encrypt_log_entry(log_entry)
        self.db.add_log_entry(encrypted_data)
        print(f"Security event logged: {event_type}")

    def get_decrypted_logs(self) -> list[Dict[str, Any]]:
        raw_logs = self.db.get_all_logs()
        decrypted_logs = []
        for log in raw_logs:
            try:
                encrypted_data = log['encrypted_log_data']
                json_data = decrypt_data(self.vault_key, encrypted_data)
                entry = json.loads(json_data)
                # Add ID for reference
                entry['id'] = log['id']
                decrypted_logs.append(entry)
            except Exception as e:
                # Log corrupted or undecryptable (e.g. from previous session with different key/random key)
                decrypted_logs.append({
                    "id": log['id'],
                    "timestamp": log['timestamp'],
                    "event_type": "ENCRYPTED/UNREADABLE",
                    "details": {"error": "Impossible de déchiffrer cet événement."}
                })
        return decrypted_logs

    def get_decrypted_photo(self, filename: str) -> bytes:
        path = os.path.join(config.SECURITY_PHOTO_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError("Fichier photo introuvable.")
        with open(path, 'rb') as f:
            return decrypt_binary(self.vault_key, f.read())

    def cleanup_old_logs(self, hours: int = 24) -> int:
        """Deletes logs older than the specified number of hours."""
        count = self.db.delete_old_logs(hours)
        print(f"Cleaned up {count} old log entries.")
        return count

    def capture_webcam_bytes(self) -> bytes | None:
        """Captures webcam image and returns raw bytes (JPEG) without saving/encrypting yet."""
        if not config.SECURITY_PHOTO_ENABLED or not _CAMERA_AVAILABLE:
            print(f"Capture annulée: Enabled={config.SECURITY_PHOTO_ENABLED}, CameraAvailable={_CAMERA_AVAILABLE}")
            return None
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Erreur: Impossible d'ouvrir le périphérique vidéo (webcam).")
                return None
            
            # Lire quelques frames pour laisser la caméra s'ajuster (balance des blancs, etc.)
            for _ in range(5):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            
            if not ret: 
                print("Erreur: Impossible de lire une image depuis la webcam.")
                return None
            
            success, buffer = cv2.imencode('.jpg', frame)
            return buffer.tobytes() if success else None
        except Exception as e:
            print(f"Error capturing webcam: {e}")
            return None

    def save_encrypted_photo(self, raw_image_data: bytes) -> str:
        """Encrypts and saves raw image bytes, returns filename."""
        try:
            encrypted_image_data = encrypt_binary(self.vault_key, raw_image_data)
            
            photo_filename = f"security_photo_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.enc"
            photo_path = os.path.join(config.SECURITY_PHOTO_DIR, photo_filename)
            
            with open(photo_path, 'wb') as f:
                f.write(encrypted_image_data)
            
            print(f"Security photo saved: {photo_path}")
            return photo_filename
        except Exception as e:
            print(f"Error saving encrypted photo: {e}")
            return ""

    def take_security_photo(self):
        """
        Captures a webcam photo, encrypts it, and stores it locally.
        """
        if not config.SECURITY_PHOTO_ENABLED or not _CAMERA_AVAILABLE:
            self.log_event(LOG_EVENT_PHOTO_CAPTURE, {"status": "skipped", "reason": "disabled_or_missing_deps"})
            return

        try:
            raw_image_data = self.capture_webcam_bytes()
            if not raw_image_data:
                raise Exception("Failed to capture image from webcam")

            filename = self.save_encrypted_photo(raw_image_data)
            if filename:
                self.log_event(LOG_EVENT_PHOTO_CAPTURE, {"status": "success", "filename": filename})
        except Exception as e:
            self.log_event(LOG_EVENT_PHOTO_CAPTURE, {"status": "failed", "error": str(e)})
            print(f"Error capturing security photo: {e}")

    def send_test_email(self, email_settings: Dict[str, Any]):
        """Sends a test email with the provided settings."""
        try:
            msg = MIMEText("Ceci est un email de test de votre application Thanos.\n\n"
                           "Si vous recevez cet email, la configuration SMTP est correcte.")
            msg['Subject'] = "Thanos - Email de test"
            msg['From'] = email_settings['sender']
            msg['To'] = email_settings['recipient']

            with smtplib.SMTP(email_settings['server'], email_settings['port']) as server:
                server.starttls()
                if email_settings.get('username') and email_settings.get('password'):
                    server.login(email_settings['username'], email_settings['password'])
                server.send_message(msg)
            print(f"Test email sent successfully to {email_settings['recipient']}")
        except Exception as e:
            print(f"Error sending test email: {e}")
            raise  # Re-raise the exception to be caught by the caller

    def send_email_alert(self, attempts: int):
        """Sends an email alert to the configured recipient."""
        if not config.EMAIL_ALERTS_ENABLED:
            self.log_event(LOG_EVENT_EMAIL_ALERT, {"status": "skipped", "reason": "disabled"})
            return

        try:
            device_id = get_device_id()
            msg = MIMEText(f"Alerte de sécurité Thanos:\n\n"
                           f"Date et heure: {datetime.datetime.now().isoformat()}\n"
                           f"Nombre de tentatives incorrectes: {attempts}\n"
                           f"Identifiant local de l'appareil: {device_id}\n\n"
                           f"Ceci est une alerte automatique de votre coffre-fort Thanos.")
            msg['Subject'] = "Alerte de sécurité Thanos: Tentatives de connexion incorrectes"
            msg['From'] = config.EMAIL_SENDER
            msg['To'] = config.EMAIL_RECIPIENT

            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
                server.starttls()
                if config.SMTP_USERNAME and config.SMTP_PASSWORD:
                    server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(msg)
            self.log_event(LOG_EVENT_EMAIL_ALERT, {"status": "success", "recipient": config.EMAIL_RECIPIENT})
            print(f"Security email alert sent to {config.EMAIL_RECIPIENT}")
        except Exception as e:
            self.log_event(LOG_EVENT_EMAIL_ALERT, {"status": "failed", "error": str(e)})
            print(f"Error sending security email: {e}")