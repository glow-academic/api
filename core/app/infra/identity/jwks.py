"""JWKS key management for default-idp OIDC provider.

Keys are persisted to /app/uploads/.idp-key.pem so they survive container
restarts. Generated once, then reloaded from file.
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk

# Global key pair cache
_key_pair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey] | None = None

# Persist key to uploads volume (survives restarts)
_KEY_PATH = Path(os.getenv("IDP_KEY_PATH", "/app/uploads/.idp-key.pem"))


def _load_key_from_disk() -> (
    tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey] | None
):
    """Read + parse the on-disk PEM, or return None if absent/empty/corrupt."""
    try:
        pem = _KEY_PATH.read_bytes()
    except OSError:
        return None  # absent or unreadable
    if not pem:
        return None  # racing winner hasn't finished writing yet
    try:
        private_key = serialization.load_pem_private_key(pem, password=None)
    except Exception:
        return None  # corrupt / partial write
    return private_key, private_key.public_key()


def generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Return the IdP signing key, guaranteeing in-memory == on-disk.

    Create-if-absent ATOMICALLY, else adopt the on-disk key. This is the fix
    for the blue/green key divergence: both server colours share the same
    uploads volume and boot concurrently on a fresh deploy with the file
    absent. A naive check-then-generate is a TOCTOU race — every process
    generates a *different* key, last-writer-wins the file, and the losers'
    in-memory key no longer matches the persisted one, so self-minted tokens
    (verified in a fresh process that reads the file) fail "No matching JWK".

    Here the claim is atomic: ``os.open`` with ``O_CREAT | O_EXCL`` lets
    exactly ONE process create the file. The winner writes + returns its
    candidate; every loser DISCARDS its candidate and adopts the on-disk key.
    The invariant "returned key == on-disk key" therefore holds for every
    process regardless of boot order.
    """
    # Fast path: a key is already persisted → adopt it (the common case after
    # the first boot, and for the second colour once the first has written).
    existing = _load_key_from_disk()
    if existing is not None:
        return existing

    try:
        _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # read-only FS; the os.open below will fail and we'll fall back

    # Generate a candidate, but only keep it if we win the atomic claim.
    candidate = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    candidate_pem = candidate.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    try:
        # O_EXCL → only the first process to reach this line creates the file.
        fd = os.open(_KEY_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        # Lost the race: another process/colour claimed the file first. Discard
        # our candidate and adopt the on-disk key so in-memory == on-disk. The
        # winner may still be mid-write (empty/partial file), so retry briefly.
        for _ in range(100):
            on_disk = _load_key_from_disk()
            if on_disk is not None:
                return on_disk
            time.sleep(0.01)
        return candidate, candidate.public_key()  # give up; won't persist
    except OSError:
        return candidate, candidate.public_key()  # read-only FS; won't persist

    # We own the file: write our candidate and return it.
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(candidate_pem)
    except OSError:
        try:
            os.close(fd)
        except OSError:
            pass
    return candidate, candidate.public_key()


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
