"""Tests for identity state token signing and verification."""

from __future__ import annotations

import os
import time

import pytest
from jose import jwt

# Ensure AUTH_CLIENT_SECRET is set for tests
os.environ.setdefault("AUTH_CLIENT_SECRET", "test-secret-for-state-tests")

from app.infra.identity.state import (
    get_auth_secret,
    sign_state_token,
    verify_state_token,
)

pytestmark = pytest.mark.asyncio


async def test_sign_and_verify_roundtrip():
    """A signed state token can be verified and returns correct payload."""
    token = sign_state_token(
        department_id="dept-123",
        mode="guest",
        nonce="abc123",
    )
    payload = verify_state_token(token)

    assert payload["department_id"] == "dept-123"
    assert payload["mode"] == "guest"
    assert payload["nonce"] == "abc123"
    assert "iat" in payload
    assert "exp" in payload


async def test_sign_state_token_with_none_department():
    """department_id can be None for default settings."""
    token = sign_state_token(
        department_id=None,
        mode="default-account",
        nonce="xyz789",
    )
    payload = verify_state_token(token)

    assert payload["department_id"] is None
    assert payload["mode"] == "default-account"


async def test_verify_rejects_expired_token():
    """An expired token raises ExpiredSignatureError."""
    import asyncio

    # Sign with 1 second expiry
    token = sign_state_token(
        department_id="dept-1",
        mode="guest",
        nonce="n1",
        expires_in=1,
    )

    # Wait for token to expire
    await asyncio.sleep(2)

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_state_token(token)


async def test_verify_rejects_tampered_token():
    """A token with modified content fails verification."""
    token = sign_state_token(
        department_id="dept-1",
        mode="guest",
        nonce="n1",
    )
    # Tamper with the token payload
    tampered = token[:-5] + "XXXXX"

    with pytest.raises(jwt.JWTError):
        verify_state_token(tampered)


async def test_verify_rejects_invalid_mode():
    """A token with an unsupported mode raises JWTError."""
    secret = get_auth_secret()
    now = int(time.time())

    bad_token = jwt.encode(
        {
            "department_id": "dept-1",
            "mode": "invalid-mode",
            "nonce": "n1",
            "iat": now,
            "exp": now + 120,
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(jwt.JWTError, match="Invalid mode"):
        verify_state_token(bad_token)


async def test_verify_rejects_missing_fields():
    """A token missing required fields raises JWTError."""
    secret = get_auth_secret()
    now = int(time.time())

    # Missing nonce
    bad_token = jwt.encode(
        {
            "department_id": "dept-1",
            "mode": "guest",
            "iat": now,
            "exp": now + 120,
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(jwt.JWTError, match="Missing required fields"):
        verify_state_token(bad_token)


async def test_get_auth_secret_returns_consistent_value():
    """get_auth_secret returns the same value on repeated calls."""
    secret1 = get_auth_secret()
    secret2 = get_auth_secret()
    assert secret1 == secret2
    assert len(secret1) > 0
