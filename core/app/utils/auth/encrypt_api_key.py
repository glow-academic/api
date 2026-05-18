"""Encrypt API key using AES-256-CBC with PBKDF2 key derivation."""

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from dotenv import load_dotenv

from app.utils.auth.derive_key import IV_LENGTH, SALT_LENGTH, derive_key

load_dotenv()


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key using AES-256-CBC with PBKDF2 key derivation (matching TypeScript implementation)"""
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is not set")

    # Generate random salt and IV
    salt = os.urandom(SALT_LENGTH)
    iv = os.urandom(IV_LENGTH)

    # Derive the key using PBKDF2
    key = derive_key(secret_key, salt)

    # Add PKCS7 padding
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(api_key.encode("utf-8")) + padder.finalize()

    # Create cipher and encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

    # Combine salt + iv + encrypted data
    combined = salt + iv + encrypted_data

    # Return base64 encoded string
    return base64.b64encode(combined).decode("utf-8")
