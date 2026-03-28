"""Tests for prepare_pipeline — pure functions for generation preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from app.infra.websocket.prepare_pipeline import (
    build_namespaced_context,
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
        resource_types_raw=["names"],
        artifact_type="persona",
        valid_resource_types=["names", "descriptions"],
        entry_types=[],
        requires_draft=False,
        draft_id=None,
    )
    assert err is None


async def test_validate_payload_rejects_empty_resource_types():
    """Empty resource_types returns an error message."""
    err = validate_payload(
        resource_types_raw=[],
        artifact_type="persona",
        valid_resource_types=["names"],
        entry_types=[],
        requires_draft=False,
        draft_id=None,
    )
    assert err is not None
    assert "resource_types must be provided" in err


async def test_validate_payload_rejects_invalid_resource_types():
    """Invalid resource types return an error listing them."""
    err = validate_payload(
        resource_types_raw=["names", "bogus"],
        artifact_type="persona",
        valid_resource_types=["names"],
        entry_types=[],
        requires_draft=False,
        draft_id=None,
    )
    assert err is not None
    assert "bogus" in err


async def test_validate_payload_requires_draft_when_flag_set():
    """requires_draft=True and no draft_id yields an error."""
    err = validate_payload(
        resource_types_raw=["names"],
        artifact_type="cohort",
        valid_resource_types=["names"],
        entry_types=[],
        requires_draft=True,
        draft_id=None,
    )
    assert err is not None
    assert "draft_id is required" in err


async def test_validate_payload_accepts_entry_types():
    """Entry types are also valid resource types."""
    err = validate_payload(
        resource_types_raw=["messages"],
        artifact_type="persona",
        valid_resource_types=["names"],
        entry_types=["messages"],
        requires_draft=False,
        draft_id=None,
    )
    assert err is None


async def test_build_namespaced_context_structures_artifacts():
    """build_namespaced_context nests results under artifacts.{name}.{operation}."""
    artifact_results = {
        "persona": {"get": {"resources": {"names": [{"name": "Alice"}]}}},
    }
    context = build_namespaced_context(artifact_results)

    assert "artifacts" in context
    assert "persona" in context["artifacts"]
    assert "get" in context["artifacts"]["persona"]
    assert context["artifacts"]["persona"]["get"]["resources"]["names"][0]["name"] == "Alice"


async def test_build_namespaced_context_merges_entry_results():
    """Entry results are merged into the artifacts namespace."""
    artifact_results = {"persona": {"get": {"data": "x"}}}
    entry_results = {"persona": {"search": {"entries": []}}}

    context = build_namespaced_context(artifact_results, entry_results)

    assert "get" in context["artifacts"]["persona"]
    assert "search" in context["artifacts"]["persona"]


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
