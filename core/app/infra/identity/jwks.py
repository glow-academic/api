"""JWKS key management for default-idp OIDC provider.

Keys are persisted to /app/uploads/.idp-key.pem so they survive container
restarts. Generated once, then reloaded from file.
"""

import hashlib
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk

# Global key pair cache
_key_pair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey] | None = None

# Persist key to uploads volume (survives restarts)
_KEY_PATH = Path(os.getenv("IDP_KEY_PATH", "/app/uploads/.idp-key.pem"))


def generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Load persisted key or generate and save a new one."""
    # Try to load existing key
    if _KEY_PATH.exists():
        try:
            pem = _KEY_PATH.read_bytes()
            private_key = serialization.load_pem_private_key(pem, password=None)
            return private_key, private_key.public_key()
        except Exception:
            pass  # Corrupt file, regenerate

    # Generate new key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Persist to file
    try:
        _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEY_PATH.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    except Exception:
        pass  # Read-only filesystem, key won't persist

    return private_key, private_key.public_key()


def get_or_create_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Get existing key pair or create a new one."""
    global _key_pair
    if _key_pair is None:
        _key_pair = generate_key_pair()
    return _key_pair


def get_private_key() -> rsa.RSAPrivateKey:
    """Get the private key for signing tokens."""
    private_key, _ = get_or_create_key_pair()
    return private_key


def get_public_key() -> rsa.RSAPublicKey:
    """Get the public key for token verification."""
    _, public_key = get_or_create_key_pair()
    return public_key


def get_jwks() -> dict[str, Any]:
    """Get JWKS (JSON Web Key Set) for public key exposure."""
    public_key = get_public_key()

    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    jwk_dict = jwk.construct(pem, algorithm="RS256")
    public_jwk = jwk_dict.to_dict()

    public_jwk["kid"] = get_key_id()
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"

    return {"keys": [public_jwk]}


def get_key_id() -> str:
    """Get the key ID — stable based on the actual public key."""
    public_key = get_public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return f"glow-idp-{hashlib.sha256(pub_bytes).hexdigest()[:16]}"
