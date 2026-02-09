# thanos_app/core/crypto.py
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import bcrypt
import argon2
from argon2.low_level import Type as Argon2Type
import secrets

# Argon2id parameters for key derivation (desktop app)
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 262144  # 256 MiB
ARGON2_PARALLELISM = os.cpu_count() or 2 # Use detected CPU cores, fallback to 2
ARGON2_HASH_LEN = 32 # For a 256-bit key (AES-256)
ARGON2_SALT_BYTES = 16 # Recommended salt length

def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derives a 256-bit key from the master password using Argon2id.
    This is the modern, recommended standard for password-based key derivation.
    """
    return argon2.low_level.hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Argon2Type.ID
    )

def encrypt_data(key: bytes, plaintext: str) -> bytes:
    data_to_encrypt = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data_to_encrypt, None)
    return nonce + ciphertext

def decrypt_data(key: bytes, encrypted_data: bytes, decode_to_str: bool = True) -> bytes | str:
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    aesgcm = AESGCM(key)
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8') if decode_to_str else plaintext_bytes
    except Exception as e:
        raise ValueError("Échec du déchiffrement.") from e

def encrypt_binary(key: bytes, data: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext

def decrypt_binary(key: bytes, encrypted_data: bytes) -> bytes:
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password: str, hashed_password: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def generate_recovery_key() -> str:
    """Génère une clé de récupération aléatoire (URL-safe base64)."""
    return secrets.token_urlsafe(24)
