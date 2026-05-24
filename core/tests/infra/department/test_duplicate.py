"""Tests for department duplicate — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.department.duplicate import duplicate_department_impl

pytestmark = pytest.mark.asyncio(loop_scope="session")

_PROFILE_ID = uuid4()


@dataclass
class _FakeProfile:
    profiles_id = uuid4()
    name = "Test User"
    role = "admin"
    role_name = "Admin"
    role_description = "Administrator"
    role_artifacts = []
    primary_email = "test@test.com"
    emails = ["test@test.com"]
    primary_department_id = None
    department_ids = []
    settings_id = None
    request_limit = None
    request_limit_interval = None
    is_active = True
    session_id = None
    group_id = uuid4()
    role_level = 1
    role_permissions = []


class _FakeConn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._FakeTx()

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _FakePool:
    class _ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(*args, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.department.duplicate.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await duplicate_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.department.duplicate.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await duplicate_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(duplicate_department_impl)
