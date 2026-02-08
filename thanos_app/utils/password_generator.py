# thanos_app/utils/password_generator.py
import secrets
import string
def generate_password(length: int = 16, use_uppercase: bool = True, use_digits: bool = True, use_symbols: bool = True) -> str:
    alphabet = string.ascii_lowercase
    if use_uppercase: alphabet += string.ascii_uppercase
    if use_digits: alphabet += string.digits
    if use_symbols: alphabet += string.punctuation
    if length < 8: raise ValueError("Min length 8")
    return ''.join(secrets.choice(alphabet) for _ in range(length))
