"""Tests for export_test_impl — export orchestration."""
import csv
import io
import zipfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
pytestmark = pytest.mark.asyncio

async def test_export_raises_401_when_no_profile(monkeypatch):
    import app.infra.test.export as mod
    monkeypatch.setattr(mod, "resolve_profile_identity_context", AsyncMock(return_value=None))
    pool, redis = AsyncMock(), AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    # view='single' needs a test_id to reach the profile-resolution auth
    # check; without it the impl validation-rejects with 400 first.
    with pytest.raises(HTTPException) as exc:
        await mod.export_test_impl(
            pool, redis, profile_id=uuid4(), test_id=uuid4()
        )
    assert exc.value.status_code == 401

async def test_export_function_exists():
    import app.infra.test.export as mod
    assert callable(mod.export_test_impl)

async def test_export_module_has_csv_columns():
    import app.infra.test.export as mod
    csv_attrs = [a for a in dir(mod) if a.endswith("_CSV_COLUMNS") or a.endswith("_COLUMNS")]
    assert len(csv_attrs) >= 1 or hasattr(mod, "PIPE")


def _acquire_pool() -> MagicMock:
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_single_export_with_runs_sources_agents_from_invocation_and_bundle_from_trace(
    monkeypatch,
):
    """Regression for #108: the runs.csv path must read agents off the parent
    invocation and the prompt/instruction/tool/voice bundle off the linked
    trace — runs carry none of these after the runs→traces refactor (#102).
    Previously this path raised AttributeError on ``run.agent_ids``.
    """
    import app.infra.test.export as mod
    from app.tools.entries.test.types import GetTestResponse
    from app.tools.entries.test_invocation.types import GetTestInvocationResponse
    from app.tools.entries.test_invocation_runs.types import (
        GetTestInvocationRunsResponse,
    )
    from app.tools.entries.test_invocation_traces.types import (
        GetTestInvocationTracesResponse,
    )
    from app.tools.resources.names.types import GetNameResponse
    from app.tools.resources.voices.types import GetVoiceResponse

    now = datetime(2026, 1, 1, 12, 0, 0)
    test_id = uuid4()
    inv_id = uuid4()
    trace_id = uuid4()
    run_id = uuid4()

    agent_id = uuid4()
    prompt_id = uuid4()
    instruction_id = uuid4()
    tool_id = uuid4()
    voice_id = uuid4()

    test = GetTestResponse(
        test_id=test_id, call_id=None, eval_id=None, profile_id=None,
        department_ids=[], test_name="T", test_description="d",
        num_invocations=1, infinite_mode=False, is_dynamic=False,
        archived=False, test_created_at=now,
    )
    invocation = GetTestInvocationResponse(
        invocation_id=inv_id, test_id=test_id, group_id=None,
        invocation_created_at=now, invocation_title="inv", use_custom=False,
        position=0, invocation_completed=False, grade_id=None,
        grade_score=None, grade_passed=None, grade_time_taken=None,
        rubric_id=None, agent_ids=[agent_id], quality_id=None,
        department_ids=[], voice_id=None, temperature_level_id=None,
        reasoning_level_id=None, modality_ids=[],
    )
    trace = GetTestInvocationTracesResponse(
        id=trace_id, test_invocation_id=inv_id, run_id=None,
        created_at=now, updated_at=now, generated=False, mcp=False,
        active=True, voice_ids=[voice_id], prompt_ids=[prompt_id],
        instruction_ids=[instruction_id], tool_ids=[tool_id],
    )
    run = GetTestInvocationRunsResponse(
        id=run_id, test_invocation_id=inv_id,
        test_invocation_traces_id=trace_id, run_id=None,
        created_at=now, updated_at=now, generated=False, mcp=False, active=True,
    )

    def _name(nid, label):
        return GetNameResponse(id=nid, name=label, created_at=now, active=True,
                               mcp=False, generated=False)

    names = [
        _name(agent_id, "AgentName"),
        _name(prompt_id, "PromptName"),
        _name(instruction_id, "InstructionName"),
        _name(tool_id, "ToolName"),
    ]
    voices = [GetVoiceResponse(id=voice_id, voice="VoiceName", created_at=now,
                              active=True, mcp=False, generated=False)]

    monkeypatch.setattr(mod, "resolve_profile_identity_context",
                        AsyncMock(return_value=object()))
    monkeypatch.setattr(mod, "search_tests",
                        AsyncMock(return_value=([test], 1)))
    monkeypatch.setattr(mod, "search_test_invocation_entries_internal",
                        AsyncMock(return_value=([invocation], 1)))
    monkeypatch.setattr(mod, "search_test_invocation_runs",
                        AsyncMock(return_value=([run], 1)))
    monkeypatch.setattr(mod, "search_test_invocation_traces",
                        AsyncMock(return_value=([trace], 1)))
    monkeypatch.setattr(mod, "get_names", AsyncMock(return_value=names))
    monkeypatch.setattr(mod, "get_departments", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_voices", AsyncMock(return_value=voices))

    pool, redis = _acquire_pool(), AsyncMock()
    bytes_, row_count = await mod._export_single_test_bytes(
        pool, redis, profile_id=uuid4(), test_id=test_id,
    )

    assert row_count == 3  # 1 test + 1 invocation + 1 run
    with zipfile.ZipFile(io.BytesIO(bytes_)) as zf:
        runs_csv = zf.read("runs.csv").decode("utf-8")
    rows = list(csv.reader(io.StringIO(runs_csv)))
    header, data = rows[0], rows[1]
    record = dict(zip(header, data))
    assert record["id"] == str(run_id)
    assert record["agents"] == "AgentName"        # from parent invocation
    assert record["voices"] == "VoiceName"        # from linked trace
    assert record["prompts"] == "PromptName"
    assert record["instructions"] == "InstructionName"
    assert record["tools"] == "ToolName"
