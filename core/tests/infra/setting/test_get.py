"""Tests for setting get — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.setting.get import get_setting_impl

pytestmark = pytest.mark.asyncio(loop_scope="session")

_PROFILE_ID = uuid4()


class TestGetAuth:
    async def test_raises_401_when_common_context_returns_none(self, monkeypatch):
        """When profile is not found, should raise 401."""
        async def fake_resolve(*args, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.setting.get.resolve_common_context",
            fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_setting_impl(
                object(), object(), profile_id=_PROFILE_ID, setting_id=None,
            )
        assert exc_info.value.status_code == 401


class TestGetResolves:
    async def test_common_context_is_called(self, monkeypatch):
        """Verify the function calls resolve_common_context."""
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return None  # Will cause 401

        monkeypatch.setattr(
            "app.infra.setting.get.resolve_common_context",
            fake_resolve,
        )

        with pytest.raises(HTTPException):
            await get_setting_impl(
                object(), object(), profile_id=_PROFILE_ID, setting_id=None,
            )
        assert len(called) == 1


class TestGetImport:
    async def test_function_is_importable(self):
        assert callable(get_setting_impl)
