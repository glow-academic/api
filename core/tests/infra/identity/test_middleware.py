"""Tests for identity middleware — require_auth dependency."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.infra.identity.middleware import require_auth
from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio


def _make_request():
    """Create a mock Request object with mutable state."""
    request = MagicMock()
    request.state = MagicMock()
    return request


async def test_require_auth_raises_401_without_credentials():
    """Missing Authorization header raises 401."""
    request = _make_request()
    with pytest.raises(HTTPException) as exc_info:
        await require_auth(request, credentials=None)

    assert exc_info.value.status_code == 401
    assert "Missing Authorization" in exc_info.value.detail


async def test_require_auth_sets_request_state_on_success():
    """Valid credentials set profile_id, session_id, identity on request.state."""
    profile_id = uuid4()
    session_id = uuid4()
    identity = Identity(
        profile_id=profile_id,
        session_id=session_id,
        email="user@test.com",
        role="student",
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-jwt-token",
    )
    request = _make_request()

    with patch(
        "app.infra.identity.middleware.resolve_identity",
        new_callable=AsyncMock,
        return_value=identity,
    ):
        with patch("app.infra.identity.middleware.get_pool", return_value=MagicMock()):
            result = await require_auth(request, credentials=credentials)

    assert result is identity
    assert request.state.profile_id == str(profile_id)
    assert request.state.session_id == str(session_id)
    assert request.state.identity is identity


async def test_require_auth_raises_401_on_invalid_token():
    """Invalid JWT raises 401 via ValueError from resolve_identity."""
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="bad-token",
    )
    request = _make_request()

    with patch(
        "app.infra.identity.middleware.resolve_identity",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid token"),
    ):
        with patch("app.infra.identity.middleware.get_pool", return_value=MagicMock()):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request, credentials=credentials)

    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail


async def test_require_auth_returns_identity_object():
    """The returned Identity can be used by downstream dependencies."""
    identity = Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        is_mcp=True,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="mcp-token",
    )
    request = _make_request()

    with patch(
        "app.infra.identity.middleware.resolve_identity",
        new_callable=AsyncMock,
        return_value=identity,
    ):
        with patch("app.infra.identity.middleware.get_pool", return_value=MagicMock()):
            result = await require_auth(request, credentials=credentials)

    assert result.is_mcp is True
    assert result.profile_id == identity.profile_id
