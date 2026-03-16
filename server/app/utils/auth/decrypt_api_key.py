"""Decrypt API key using AES-256-CBC with PBKDF2 key derivation."""

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from dotenv import load_dotenv

from app.utils.auth.derive_key import IV_LENGTH, SALT_LENGTH, derive_key

load_dotenv()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key using the same method as the TypeScript encryptProviderKey/decryptProviderKey functions"""
    # Handle None or empty string
    if not encrypted_key:
        raise ValueError(
            "API key is missing - scenario/persona/provider chain is broken."
        )

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is not set")

    # Decode the base64 combined data
    combined = base64.b64decode(encrypted_key)

    # Extract components (salt + iv + encrypted data)
    salt = combined[:SALT_LENGTH]
    iv = combined[SALT_LENGTH : SALT_LENGTH + IV_LENGTH]
    encrypted_data = combined[SALT_LENGTH + IV_LENGTH :]

    # Derive the key using PBKDF2
    key = derive_key(secret_key, salt)

    # Create cipher and decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    # Decrypt the data
    decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()

    # Remove PKCS7 padding using standard unpadder
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

    return decrypted.decode("utf-8")
