"""State token signing and verification for default-idp OAuth flow."""

import os
import time
from typing import Any

from jose import jwt


def get_auth_secret() -> str:
    """Get AUTH_SECRET from environment."""
    secret = os.getenv("AUTH_SECRET")
    if not secret:
        raise ValueError("AUTH_SECRET environment variable is required")
    return secret


def sign_state_token(
    department_id: str | None,
    mode: str,
    nonce: str,
    expires_in: int = 120,
) -> str:
    """Sign a state token with department_id, mode, nonce, and expiry.

    Args:
        department_id: Department ID (can be None for default settings)
        mode: Auth mode ("guest" or "default-account")
        nonce: Random nonce for replay protection
        expires_in: Token expiry in seconds (default 120)

    Returns:
        Signed JWT token string
    """
    secret = get_auth_secret()
    now = int(time.time())

    payload: dict[str, Any] = {
        "department_id": department_id,
        "mode": mode,
        "nonce": nonce,
        "iat": now,
        "exp": now + expires_in,
    }

    return jwt.encode(payload, secret, algorithm="HS256")


def verify_state_token(token: str) -> dict[str, Any]:
    """Verify and decode a state token.

    Args:
        token: Signed JWT token string

    Returns:
        Decoded payload dictionary

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.JWTError: If token is invalid or signature verification fails
    """
    secret = get_auth_secret()

    payload = jwt.decode(token, secret, algorithms=["HS256"])

    # Validate required fields
    if (
        "department_id" not in payload
        or "mode" not in payload
        or "nonce" not in payload
    ):
        raise jwt.JWTError("Missing required fields in state token")

    # Validate mode
    if payload["mode"] not in ("guest", "default-account"):
        raise jwt.JWTError(f"Invalid mode: {payload['mode']}")

    return payload
