"""Derive encryption key using PBKDF2."""

import base64
import hashlib

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

IV_LENGTH = 16
SALT_LENGTH = 32
KEY_LENGTH = 32
PBKDF2_ITERATIONS = 100000


def derive_from_secret_key(secret_key: str, purpose: str) -> str:
    """Derive a deterministic string from SECRET_KEY for a given purpose.

    Used for AUTH_SECRET and AUTH_KEYCLOAK_SECRET when not explicitly set.
    Same input always produces same output (fixed salt from purpose).
    """
    salt = hashlib.sha256(f"glow-{purpose}-v1".encode()).digest()
    derived = derive_key(secret_key, salt)
    return base64.urlsafe_b64encode(derived).decode().rstrip("=")


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
