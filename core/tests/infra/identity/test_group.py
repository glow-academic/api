"""Tests for identity group resolution — resolve_group priority chain."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.infra.identity.group import resolve_group

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeAttempt:
    profile_id: object
    infinite_mode: bool = False


@dataclass
class _FakeChat:
    chat_id: object
    group_id: object
    completed: bool = False
    time_limit_seconds: int = 0
    grade_time_taken: int | None = None
    chat_created_at: object = None


@dataclass
class _FakeGroup:
    id: object


async def test_resolve_group_creates_fresh_group_with_session(conn, session_id):
    """Priority 4: creates a fresh group when no attempt/test/draft given."""
    profiles_id = uuid4()
    result = await resolve_group(
        conn,
        profiles_id=profiles_id,
        session_id=session_id,
    )
    assert result.group_id is not None
    assert result.show_controls is False


async def test_resolve_group_raises_without_session_or_profile():
    """Raises ValueError when no session_id and no profile_id provided."""
    conn = AsyncMock()
    with pytest.raises(ValueError, match="profile"):
        await resolve_group(conn, profiles_id=None, session_id=None)


async def test_resolve_group_raises_without_session_but_with_profile():
    """Raises ValueError when profile given but session_id missing."""
    conn = AsyncMock()
    with pytest.raises(ValueError, match="session_id"):
        await resolve_group(
            conn,
            profiles_id=uuid4(),
            session_id=None,
        )


