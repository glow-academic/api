"""Derive encryption key using PBKDF2."""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

IV_LENGTH = 16
SALT_LENGTH = 32
KEY_LENGTH = 32
PBKDF2_ITERATIONS = 100000


def derive_key(password: str, salt: bytes) -> bytes:
    """Generate a key from the secret using PBKDF2 (matching Node.js implementation)"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(password.encode("utf-8"))
