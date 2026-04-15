"""Tests for prepare_pipeline — pure functions for generation preparation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.infra.websocket.prepare_pipeline import (
    compute_all_artifact_types,
    compute_createable_resources,
    enrich_tools_with_args,
    enrich_tools_with_args_outputs,
    validate_payload,
)

pytestmark = pytest.mark.asyncio


async def test_validate_payload_returns_none_when_valid():
    """Valid payload returns None (no error)."""
    err = validate_payload(
        artifact_type="persona",
        requires_draft=False,
        draft_id=None,
    )
    assert err is None


async def test_validate_payload_ignores_deprecated_resource_types_params():
    """resource_types params are accepted but ignored (no validation)."""
    err = validate_payload(
        resource_types_raw=[],
        artifact_type="persona",
        valid_resource_types=["names"],
        entry_types=[],
        requires_draft=False,
        draft_id=None,
    )
    assert err is None

    err = validate_payload(
        resource_types_raw=["names", "bogus"],
        artifact_type="persona",
        valid_resource_types=["names"],
        entry_types=[],
        requires_draft=False,
        draft_id=None,
    )
    assert err is None


async def test_validate_payload_requires_draft_when_flag_set():
    """requires_draft=True and no draft_id yields an error."""
    err = validate_payload(
        artifact_type="cohort",
        requires_draft=True,
        draft_id=None,
    )
    assert err is not None
    assert "draft_id is required" in err


async def test_compute_createable_resources():
    """compute_createable_resources extracts types from tools with create operation."""

    @dataclass
    class _FakeTool:
        operation: str
        resources: list[str] | None = None
        entries: list[str] | None = None
        artifacts: list[str] | None = None

    tools = [
        _FakeTool(operation="create", resources=["names"]),
        _FakeTool(operation="search", resources=["descriptions"]),
        _FakeTool(operation="create", entries=["messages"]),
    ]
    result = compute_createable_resources(tools)

    assert "names" in result
    assert "messages" in result
    assert "descriptions" not in result


async def test_compute_all_artifact_types():
    """compute_all_artifact_types extracts unique types from tool dicts."""
    tool_dicts = [
        {"artifacts": ["persona", "cohort"]},
        {"artifacts": ["persona", "simulation"]},
        {"artifacts": None},
    ]
    result = compute_all_artifact_types(tool_dicts)

    assert set(result) == {"persona", "cohort", "simulation"}


async def test_enrich_tools_with_args_returns_unchanged_when_no_args():
    """Returns tool_dicts unchanged when no config_args provided."""
    tools = [{"name": "search", "id": "1"}]
    result = enrich_tools_with_args(tools, [], [])
    assert result is tools


async def test_enrich_tools_with_args_outputs_returns_unchanged_when_empty():
    """Returns tool_dicts unchanged when no config_args_outputs."""
    tools = [{"name": "search", "id": "1"}]
    result = enrich_tools_with_args_outputs(tools, [], [])
    assert result is tools
