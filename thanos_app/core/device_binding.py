# thanos_app/core/device_binding.py
import uuid
import hashlib
import socket
import os

def get_device_fingerprint() -> str:
    """
    Génère une empreinte unique de l'appareil (Device Fingerprint).
    Combine : /etc/machine-id (Linux), hostname, et adresse MAC.
    Retourne un hash SHA-256.
    """
    # 1. Machine ID (Spécifique Linux, stable entre les redémarrages)
    machine_id = ""
    # On cherche dans les emplacements standards
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    machine_id = f.read().strip()
                break
            except Exception:
                pass

    # 2. Hostname
    hostname = socket.gethostname()

    # 3. Adresse MAC (getnode retourne l'entier 48-bit)
    mac_address = str(uuid.getnode())

    # 4. Concaténation des informations
    raw_data = f"{machine_id}|{hostname}|{mac_address}"
    
    # 5. Génération du hash SHA-256
    return hashlib.sha256(raw_data.encode('utf-8')).hexdigest()

def get_device_id() -> str:
    mac_address = uuid.getnode()
    return hashlib.sha256(str(mac_address).encode()).hexdigest()

def combine_key_with_device_id(derived_key: bytes, device_id: str) -> bytes:
    combined = derived_key + device_id.encode('utf-8')
    final_key = hashlib.sha256(combined).digest()
    return final_key
