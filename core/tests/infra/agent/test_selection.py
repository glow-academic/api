"""Tests for agent selection — scoring and best-agent selection logic."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infra.agent.selection import (
    has_tools_for_resource,
    score_agent_for_artifact,
    select_agents_for_artifact,
    select_best_agent_for_resource,
    select_multi_resource_agent,
)
from app.infra.api_types import CandidateAgent

pytestmark = pytest.mark.asyncio


def _make_candidate(
    tool_resources=None,
    department_ids=None,
    is_active=True,
    is_mcp=False,
    updated_at=None,
):
    return CandidateAgent(
        agent_id=uuid4(),
        agent_name="test-agent",
        tool_resources=set(tool_resources or []),
        create_tool_ids={},
        link_tool_ids={},
        department_ids=set(department_ids or []),
        updated_at=updated_at or datetime.now(timezone.utc),
        is_active=is_active,
        is_mcp=is_mcp,
    )


# ---------- score_agent_for_artifact ----------


async def test_score_higher_for_more_artifact_matches():
    agent = _make_candidate(tool_resources={"names", "descriptions", "models"})
    artifact_resources = {"names", "descriptions", "models", "prompts"}

    score = score_agent_for_artifact(agent, artifact_resources)
    assert score[0] == 3  # matched_artifact_count


async def test_score_penalizes_extra_outside_resources():
    agent = _make_candidate(
        tool_resources={"names", "descriptions", "tools", "voices"}
    )
    artifact_resources = {"names", "descriptions"}

    score = score_agent_for_artifact(agent, artifact_resources)
    assert score[0] == 2  # matched
    assert score[1] == -2  # penalty for extra outside resources


async def test_score_dept_preference_matching():
    dept = uuid4()
    agent = _make_candidate(
        tool_resources={"names"}, department_ids={dept}
    )
    score = score_agent_for_artifact(agent, {"names"}, user_department_ids={dept})
    assert score[2] == 0  # match

    score2 = score_agent_for_artifact(agent, {"names"}, user_department_ids={uuid4()})
    assert score2[2] == -1  # no match


# ---------- select_best_agent_for_resource ----------


async def test_select_best_agent_for_resource_picks_active():
    active = _make_candidate(tool_resources={"names"})
    inactive = _make_candidate(tool_resources={"names"}, is_active=False)

    result = select_best_agent_for_resource(
        [active, inactive], {"names"}, "names"
    )
    assert result == active.agent_id


async def test_select_best_agent_returns_none_when_no_match():
    agent = _make_candidate(tool_resources={"descriptions"})
    result = select_best_agent_for_resource([agent], {"names"}, "names")
    assert result is None


async def test_select_best_agent_prefers_specialist():
    generalist = _make_candidate(
        tool_resources={"names", "descriptions", "tools", "voices"}
    )
    specialist = _make_candidate(tool_resources={"names", "descriptions"})

    result = select_best_agent_for_resource(
        [generalist, specialist], {"names", "descriptions"}, "names"
    )
    assert result == specialist.agent_id


# ---------- select_agents_for_artifact ----------


async def test_select_agents_returns_dict_per_resource():
    agent = _make_candidate(tool_resources={"names", "descriptions"})

    result = select_agents_for_artifact(
        [agent], {"names", "descriptions"}, ["names", "descriptions"]
    )
    assert result["names"] == agent.agent_id
    assert result["descriptions"] == agent.agent_id


async def test_select_agents_none_for_uncovered_resource():
    agent = _make_candidate(tool_resources={"names"})

    result = select_agents_for_artifact(
        [agent], {"names", "prompts"}, ["names", "prompts"]
    )
    assert result["names"] == agent.agent_id
    assert result["prompts"] is None


# ---------- select_multi_resource_agent ----------


async def test_multi_resource_agent_requires_all_resources():
    partial = _make_candidate(tool_resources={"names"})
    full = _make_candidate(tool_resources={"names", "descriptions", "models"})

    result = select_multi_resource_agent(
        [partial, full],
        required_resources={"names", "descriptions"},
        artifact_resources={"names", "descriptions", "models"},
    )
    assert result == full.agent_id


async def test_multi_resource_agent_returns_none_when_no_match():
    agent = _make_candidate(tool_resources={"names"})
    result = select_multi_resource_agent(
        [agent],
        required_resources={"names", "descriptions"},
        artifact_resources={"names", "descriptions"},
    )
    assert result is None


async def test_select_best_agent_mcp_filter():
    non_mcp = _make_candidate(tool_resources={"names"}, is_mcp=False)
    mcp = _make_candidate(tool_resources={"names"}, is_mcp=True)

    result = select_best_agent_for_resource(
        [non_mcp, mcp], {"names"}, "names", require_mcp=True
    )
    assert result == mcp.agent_id


# ---------- has_tools_for_resource ----------


async def test_has_tools_for_resource_true():
    from dataclasses import dataclass

    @dataclass
    class FakeEntry:
        agent_id: object = None
        tool_id: object = None
        resource: str = "names"
        entry: str | None = None
        artifact: str | None = None
        is_creatable: bool = False

        @property
        def type_name(self):
            return self.resource or self.entry or self.artifact

    entries = [FakeEntry(resource="names"), FakeEntry(resource="descriptions")]
    assert has_tools_for_resource(entries, "names") is True
    assert has_tools_for_resource(entries, "prompts") is False
