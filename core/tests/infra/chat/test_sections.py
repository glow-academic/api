"""Tests for chat sections — build_chat_get_result and section builder."""

from uuid import uuid4

import pytest

from app.infra.chat.sections import _build_chat_section, build_chat_get_result
from app.infra.tool_graph import ArtifactToolScores, ResolvedTool
from app.infra.types import ArtifactContext, ResourcePair

pytestmark = pytest.mark.asyncio


def _empty_scores():
    return ArtifactToolScores(best={}, has_any={})


def _make_context(resources=None, entries=None, group_id=None):
    return ArtifactContext(
        artifact_id=uuid4(),
        active=True,
        group_id=group_id or uuid4(),
        draft_version=None,
        resources=resources or {},
        entries=entries or {},
    )


def _make_resolved_tool(target="names"):
    return ResolvedTool(
        system_id=uuid4(),
        agent_id=uuid4(),
        tool_id=uuid4(),
        operation="create",
        target_type="resource",
        target=target,
    )


async def test_build_chat_section_returns_empty_section_for_missing_resource():
    ctx = _make_context(resources={})
    scores = _empty_scores()
    section = _build_chat_section("names", context=ctx, scores=scores)
    assert section.show is True
    assert section.required is False
    assert section.current is None


async def test_build_chat_section_populates_current_from_resource_pair():
    selected = [{"id": str(uuid4()), "name": "Alice"}]
    ctx = _make_context(resources={"names": ResourcePair(selected=selected, suggestions=[])})
    scores = _empty_scores()
    section = _build_chat_section("names", context=ctx, scores=scores)
    assert section.current == selected


async def test_build_chat_section_show_ai_generate_when_tool_exists():
    tool = _make_resolved_tool("names")
    scores = ArtifactToolScores(best={"names": tool}, has_any={"names": True})
    ctx = _make_context(resources={"names": ResourcePair(selected=[], suggestions=[])})
    section = _build_chat_section("names", context=ctx, scores=scores)
    assert section.show_ai_generate is True


async def test_build_chat_section_no_ai_generate_when_no_tool():
    scores = ArtifactToolScores(best={}, has_any={})
    ctx = _make_context(resources={"names": ResourcePair(selected=[], suggestions=[])})
    section = _build_chat_section("names", context=ctx, scores=scores)
    assert section.show_ai_generate is False


async def test_build_chat_get_result_sets_group_and_attempt_ids():
    group_id = uuid4()
    attempt_id = uuid4()
    ctx = _make_context(group_id=group_id)
    scores = _empty_scores()
    result = build_chat_get_result(
        context=ctx,
        scores=scores,
        group_id=group_id,
        chat_entry_id=None,
        attempt_id=attempt_id,
    )
    assert result.group_id == group_id
    assert result.attempt_id == attempt_id
    assert result.chat_entry_id == group_id  # falls back to group_id


async def test_build_chat_get_result_uses_chat_entry_id_when_provided():
    group_id = uuid4()
    chat_entry_id = uuid4()
    ctx = _make_context(group_id=group_id)
    scores = _empty_scores()
    result = build_chat_get_result(
        context=ctx,
        scores=scores,
        group_id=group_id,
        chat_entry_id=chat_entry_id,
        attempt_id=None,
    )
    assert result.chat_entry_id == chat_entry_id


async def test_build_chat_get_result_has_all_expected_sections():
    ctx = _make_context()
    scores = _empty_scores()
    result = build_chat_get_result(
        context=ctx,
        scores=scores,
        group_id=uuid4(),
        chat_entry_id=None,
        attempt_id=None,
    )
    assert result.names is not None
    assert result.descriptions is not None
    assert result.flags is not None
    assert result.personas is not None
    assert result.scenarios is not None
    assert result.videos is not None
    assert result.images is not None
