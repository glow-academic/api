"""A3 integration: a clamped artifact *search* drops cross-department rows.

The unit coverage in ``test_artifact_scope.py`` pins the shared clamp; this
exercises one representative real search impl end-to-end (``agent``) to prove
the clamp is actually wired into the search pipeline — a cross-department actor
receives only the rows the DETAIL ``get`` would let them open, with
``total_count`` adjusted, while a same-dept actor and a super-admin see all.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infra.agent.search import search_agent_impl

pytestmark = pytest.mark.asyncio

_DEPT_A = uuid4()
_DEPT_B = uuid4()


@dataclass
class _Profile:
    profiles_id: object = None
    role: str = "instructor"
    name: str = "Alice"
    group_id: object = None
    department_ids: list = field(default_factory=list)
    role_level: int = 1
    role_permissions: list = field(default_factory=list)


@dataclass
class _Artifact:
    id: object
    department_ids: list
    name_ids: list = field(default_factory=list)
    description_ids: list = field(default_factory=list)
    model_ids: list = field(default_factory=list)
    flag_ids: list = field(default_factory=list)
    active: bool = True
    updated_at: object = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class _Ctx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        pass


class _Pool:
    def acquire(self):
        return _Ctx()


def _wire(monkeypatch, profile, artifacts):
    agent_a, agent_b = artifacts

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    async def mock_search(conn, **kw):
        return ([agent_a.id, agent_b.id], 2)

    async def mock_soft_calls(conn, redis, **kw):
        return []

    async def mock_get_agents(conn, ids, **kw):
        return [agent_a, agent_b]

    async def mock_empty(*a, **kw):
        return []

    M = "app.infra.agent.search."
    monkeypatch.setattr(M + "resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(M + "search_agents", mock_search)
    monkeypatch.setattr(
        "app.tools.entries.soft_calls.search.search_soft_calls", mock_soft_calls
    )
    monkeypatch.setattr(M + "get_agents", mock_get_agents)
    monkeypatch.setattr(M + "get_names", mock_empty)
    monkeypatch.setattr(M + "get_models_resource", mock_empty)
    monkeypatch.setattr(M + "get_flags", mock_empty)
    monkeypatch.setattr(M + "search_departments", mock_empty)
    monkeypatch.setattr(M + "search_models_resource", mock_empty)
    monkeypatch.setattr(M + "search_tools_resource", mock_empty)
    monkeypatch.setattr(M + "search_flags", mock_empty)


async def test_cross_department_actor_does_not_receive_cross_dept_rows(monkeypatch):
    # Actor belongs only to DEPT_A. Agent A is DEPT_A; Agent B is DEPT_B-only.
    agent_a = _Artifact(id=uuid4(), department_ids=[_DEPT_A])
    agent_b = _Artifact(id=uuid4(), department_ids=[_DEPT_B])
    profile = _Profile(department_ids=[_DEPT_A], role_level=1)
    _wire(monkeypatch, profile, [agent_a, agent_b])

    result = await search_agent_impl(_Pool(), None, profile_id=uuid4())

    returned = {a.agent_id for a in result.agents}
    assert returned == {agent_a.id}  # DEPT_B agent clamped out
    assert result.total_count == 1  # decremented from 2


async def test_same_department_actor_sees_all(monkeypatch):
    agent_a = _Artifact(id=uuid4(), department_ids=[_DEPT_A])
    agent_b = _Artifact(id=uuid4(), department_ids=[_DEPT_A])
    profile = _Profile(department_ids=[_DEPT_A], role_level=1)
    _wire(monkeypatch, profile, [agent_a, agent_b])

    result = await search_agent_impl(_Pool(), None, profile_id=uuid4())

    assert {a.agent_id for a in result.agents} == {agent_a.id, agent_b.id}
    assert result.total_count == 2


async def test_superadmin_sees_all_cross_dept(monkeypatch):
    agent_a = _Artifact(id=uuid4(), department_ids=[_DEPT_A])
    agent_b = _Artifact(id=uuid4(), department_ids=[_DEPT_B])
    profile = _Profile(department_ids=[], role_level=0, role="superadmin")
    _wire(monkeypatch, profile, [agent_a, agent_b])

    result = await search_agent_impl(_Pool(), None, profile_id=uuid4())

    assert {a.agent_id for a in result.agents} == {agent_a.id, agent_b.id}
    assert result.total_count == 2
