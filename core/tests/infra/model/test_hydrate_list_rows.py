"""Tests for hydrate_model_list_rows — batched active-agent counting.

Regression guard for an N+1: the per-row ``active_agent_count`` was
resolved with one ``search_agents`` round-trip per model. These tests
monkeypatch the row collaborators and use a call-counting fake conn to
assert that (a) per-model counts are correct for N>1 models and (b) only
ONE junction query is issued regardless of N.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.infra.model.hydrate_list_rows import hydrate_model_list_rows
from app.tools.artifacts.model.types import GetModelsResponse

pytestmark = pytest.mark.asyncio

_MODULE = "app.infra.model.hydrate_list_rows"


@dataclass
class _FakeProfile:
    role_level: int = 0
    role_permissions: list = field(
        default_factory=lambda: [("model", "update"), ("model", "delete")]
    )
    department_ids: list = field(default_factory=list)


class _CountingConn:
    """Fake conn that records each fetch query + returns junction pairs.

    ``pairs`` maps models_id -> list of agent_ids for the active-agent
    junction query. Any query that isn't the junction query returns [].
    """

    def __init__(self, pairs: dict[UUID, list[UUID]]):
        self._pairs = pairs
        self.fetch_queries: list[str] = []

    async def fetch(self, query, *args):
        self.fetch_queries.append(query)
        if "agent_models_junction" in query:
            requested = set(args[0]) if args else set()
            out = []
            for models_id, agent_ids in self._pairs.items():
                if models_id in requested:
                    for aid in agent_ids:
                        out.append({"models_id": models_id, "agent_id": aid})
            return out
        return []

    async def execute(self, *a, **kw):
        return None

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None


class _Pool:
    def __init__(self, conn: _CountingConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return None

        return _Ctx()


def _model(model_resource_ids: list[UUID]) -> GetModelsResponse:
    now = datetime.now(timezone.utc)
    return GetModelsResponse(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        generated=False,
        mcp=False,
        active=True,
        name_ids=[],
        description_ids=[],
        department_ids=[],
        provider_id=None,
        model_ids=model_resource_ids,
    )


def _patch_collaborators(monkeypatch, artifacts):
    async def fake_profile(*a, **kw):
        return _FakeProfile()

    async def fake_get_models(*a, **kw):
        return artifacts

    async def fake_search_soft_calls(*a, **kw):
        return []

    async def fake_get_names(*a, **kw):
        return []

    async def fake_get_descriptions(*a, **kw):
        return []

    async def fake_get_providers(*a, **kw):
        return []

    monkeypatch.setattr(f"{_MODULE}.resolve_profile_identity_context", fake_profile)
    monkeypatch.setattr(f"{_MODULE}.get_models", fake_get_models)
    monkeypatch.setattr(f"{_MODULE}.get_names", fake_get_names)
    monkeypatch.setattr(f"{_MODULE}.get_descriptions", fake_get_descriptions)
    monkeypatch.setattr(f"{_MODULE}.get_providers_resource", fake_get_providers)
    monkeypatch.setattr(
        "app.tools.entries.soft_calls.search.search_soft_calls",
        fake_search_soft_calls,
    )


class TestBatchedAgentCount:
    async def test_per_model_counts_correct_and_single_query(self, monkeypatch):
        # Three models with distinct model_resource_ids.
        m0_res, m1_res, m2_res = uuid4(), uuid4(), uuid4()
        models = [_model([m0_res]), _model([m1_res]), _model([m2_res])]
        _patch_collaborators(monkeypatch, models)

        agent_a, agent_b = uuid4(), uuid4()
        # m0 -> 2 active agents, m1 -> 0, m2 -> 1.
        pairs = {m0_res: [agent_a, agent_b], m1_res: [], m2_res: [agent_a]}
        conn = _CountingConn(pairs)
        pool = _Pool(conn)

        rows = await hydrate_model_list_rows(
            pool, object(), profile_id=uuid4(),
            model_ids=[m.id for m in models],
        )

        assert len(rows) == 3
        by_id = {r.model_id: r for r in rows}
        # active_agent_count > 0 disables can_edit/can_delete (per
        # compute_can_edit / compute_can_delete). Profile is level-0 with
        # model update+delete perms, so a 0-count model is editable.
        assert by_id[models[0].id].can_edit is False   # 2 agents
        assert by_id[models[0].id].can_delete is False
        assert by_id[models[1].id].can_edit is True    # 0 agents
        assert by_id[models[1].id].can_delete is True
        assert by_id[models[2].id].can_edit is False   # 1 agent
        assert by_id[models[2].id].can_delete is False

        # The N+1 fix: exactly ONE junction query for N=3 models.
        junction_queries = [
            q for q in conn.fetch_queries if "agent_models_junction" in q
        ]
        assert len(junction_queries) == 1

    async def test_agent_linked_to_two_resource_ids_counts_once(self, monkeypatch):
        # One model owning two resource ids; one agent linked to both must
        # count once (DISTINCT-agent semantics of search_agents).
        res_x, res_y = uuid4(), uuid4()
        models = [_model([res_x, res_y])]
        _patch_collaborators(monkeypatch, models)

        shared_agent = uuid4()
        pairs = {res_x: [shared_agent], res_y: [shared_agent]}
        conn = _CountingConn(pairs)

        rows = await hydrate_model_list_rows(
            _Pool(conn), object(), profile_id=uuid4(),
            model_ids=[models[0].id],
        )

        assert len(rows) == 1
        # 1 distinct agent -> count > 0 -> can_edit disabled.
        assert rows[0].can_edit is False
        junction_queries = [
            q for q in conn.fetch_queries if "agent_models_junction" in q
        ]
        assert len(junction_queries) == 1
