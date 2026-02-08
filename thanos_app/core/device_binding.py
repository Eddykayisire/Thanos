# thanos_app/core/device_binding.py
import uuid
import hashlib

def get_device_id() -> str:
    mac_address = uuid.getnode()
    return hashlib.sha256(str(mac_address).encode()).hexdigest()

def combine_key_with_device_id(derived_key: bytes, device_id: str) -> bytes:
    combined = derived_key + device_id.encode('utf-8')
    final_key = hashlib.sha256(combined).digest()
    return final_key
