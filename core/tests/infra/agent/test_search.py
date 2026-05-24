"""Tests for agent search — profile check, empty results."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.agent.search import search_agent_impl

pytestmark = pytest.mark.asyncio


@dataclass
class _P:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "Alice"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _Ctx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _Pool:
    def acquire(self):
        return _Ctx()


async def test_search_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.agent.search.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await search_agent_impl(_Pool(), None, profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_search_returns_empty_when_no_results(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4())
    async def mock_search(conn, **kw):
        return ([], 0)
    async def mock_depts(conn, redis, **kw):
        return []
    monkeypatch.setattr("app.infra.agent.search.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.agent.search.search_agent_artifacts", mock_search)
    monkeypatch.setattr("app.infra.agent.search.search_departments", mock_depts)
    result = await search_agent_impl(_Pool(), None, profile_id=uuid4())
    assert result.total_count == 0
    assert result.agents == []


async def test_search_passes_actor_name(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4(), name="Bob")
    async def mock_search(conn, **kw):
        return ([], 0)
    async def mock_depts(conn, redis, **kw):
        return []
    monkeypatch.setattr("app.infra.agent.search.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.agent.search.search_agent_artifacts", mock_search)
    monkeypatch.setattr("app.infra.agent.search.search_departments", mock_depts)
    result = await search_agent_impl(_Pool(), None, profile_id=uuid4())
    assert result.actor_name == "Bob"
