"""Tests for ``app.utils.auth.derive_key``.

Focuses on ``derive_from_secret_key`` — the purpose-scoped, deterministic
deriver used to mint ``AUTH_SECRET`` / ``AUTH_KEYCLOAK_SECRET`` from a
single ``SECRET_KEY`` when they aren't explicitly configured. The raw
PBKDF2 ``derive_key`` primitive is exercised in ``test_api_key_crypto.py``;
this file owns the higher-level deterministic-string contract.
"""

from __future__ import annotations

import base64
import hashlib

from app.utils.auth.derive_key import (
    KEY_LENGTH,
    derive_from_secret_key,
    derive_key,
)


def test_derive_from_secret_key_is_deterministic():
    first = derive_from_secret_key("super-secret", "keycloak-client")
    second = derive_from_secret_key("super-secret", "keycloak-client")
    assert first == second


def test_derive_from_secret_key_varies_by_purpose():
    client = derive_from_secret_key("super-secret", "keycloak-client")
    auth = derive_from_secret_key("super-secret", "auth-secret")
    assert client != auth


def test_derive_from_secret_key_varies_by_secret():
    a = derive_from_secret_key("secret-a", "keycloak-client")
    b = derive_from_secret_key("secret-b", "keycloak-client")
    assert a != b


def test_derive_from_secret_key_is_urlsafe_b64_without_padding():
    derived = derive_from_secret_key("super-secret", "keycloak-client")
    # No ``=`` padding and only url-safe base64 alphabet characters.
    assert "=" not in derived
    assert all(ch.isalnum() or ch in "-_" for ch in derived)


def test_derive_from_secret_key_matches_manual_pbkdf2_pipeline():
    """The output equals the documented salt→PBKDF2→urlsafe-b64 pipeline."""
    secret_key = "super-secret"
    purpose = "keycloak-client"

    salt = hashlib.sha256(f"glow-{purpose}-v1".encode()).digest()
    derived_bytes = derive_key(secret_key, salt)
    expected = base64.urlsafe_b64encode(derived_bytes).decode().rstrip("=")

    assert derive_from_secret_key(secret_key, purpose) == expected


def test_derive_from_secret_key_encodes_full_key_length():
    # 32-byte key → 43 url-safe base64 chars once the single ``=`` pad is
    # stripped (ceil(32/3)*4 == 44, minus one pad char).
    assert KEY_LENGTH == 32
    derived = derive_from_secret_key("super-secret", "keycloak-client")
    assert len(derived) == 43
