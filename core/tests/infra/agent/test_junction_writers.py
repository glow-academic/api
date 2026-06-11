"""C1 regression — agent rubric/prompt/quality junctions persist on
create AND update.

Before the cross-repo hunt batch:
  * ``agent_qualities_junction`` had NO writer anywhere — qualities never
    persisted even on create.
  * ``update_agent`` (artifact) only diffed names/descriptions/departments/
    models/levels/tools/voices/agents — so editing an agent's rubric, prompt,
    or qualities silently no-op'd.

These tests record the ``upsert_multi`` calls the artifact writers issue
(deps-as-params: the junction helpers are monkeypatched to a recorder, no
DB) and assert each junction table receives the supplied ids.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.tools.artifacts.agent.create as create_mod
import app.tools.artifacts.agent.update as update_mod

pytestmark = pytest.mark.asyncio


class _FakeConn:
    """Minimal asyncpg.Connection stand-in for the artifact writers."""

    def __init__(self, agent_id):
        self._agent_id = agent_id

    async def fetchval(self, *args, **kwargs):
        return self._agent_id

    async def execute(self, *args, **kwargs):
        return "UPDATE 1"


def _record_upserts(monkeypatch, module):
    """Patch upsert_multi / upsert_single on ``module`` to a recorder.

    Returns the dict {table: resource_ids} captured from upsert_multi.
    """
    multi: dict[str, list] = {}

    async def fake_multi(conn, *, table, resource_ids, **kwargs):
        multi[table] = list(resource_ids)

    async def fake_single(conn, *, table, resource_id, **kwargs):
        multi[table] = [resource_id]

    monkeypatch.setattr(module, "upsert_multi", fake_multi)
    monkeypatch.setattr(module, "upsert_single", fake_single)
    return multi


async def test_create_agent_persists_rubric_prompt_quality(monkeypatch):
    multi = _record_upserts(monkeypatch, create_mod)
    agent_id = uuid4()
    rubric_id, prompt_id, quality_id = uuid4(), uuid4(), uuid4()

    await create_mod.create_agent(
        _FakeConn(agent_id),
        rubric_ids=[rubric_id],
        prompt_ids=[prompt_id],
        quality_ids=[quality_id],
    )

    assert multi.get("agent_rubrics_junction") == [rubric_id]
    assert multi.get("agent_prompts_junction") == [prompt_id]
    # The qualities junction had no writer at all before this fix.
    assert multi.get("agent_qualities_junction") == [quality_id]


async def test_update_agent_persists_rubric_prompt_quality(monkeypatch):
    multi = _record_upserts(monkeypatch, update_mod)
    agent_id = uuid4()
    rubric_id, prompt_id, quality_id = uuid4(), uuid4(), uuid4()

    await update_mod.update_agent(
        _FakeConn(agent_id),
        agent_id,
        rubric_ids=[rubric_id],
        prompt_ids=[prompt_id],
        quality_ids=[quality_id],
    )

    assert multi.get("agent_rubrics_junction") == [rubric_id]
    assert multi.get("agent_prompts_junction") == [prompt_id]
    assert multi.get("agent_qualities_junction") == [quality_id]


async def test_update_agent_item_model_accepts_rubric_prompt_quality_instruction():
    """UpdateAgentItem must accept the fields the client (Agent.tsx) sends —
    they were dropped before because the model lacked them entirely."""
    from app.infra.agent.types import UpdateAgentItem

    rubric_id, prompt_id, instr_id, quality_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    item = UpdateAgentItem(
        id=uuid4(),
        rubric_ids=[rubric_id],
        prompt_id=prompt_id,
        instruction_ids=[instr_id],
        quality_ids=[quality_id],
    )
    assert item.rubric_ids == [rubric_id]
    assert item.prompt_id == prompt_id
    assert item.instruction_ids == [instr_id]
    assert item.quality_ids == [quality_id]
