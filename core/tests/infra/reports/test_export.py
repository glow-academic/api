"""Integration tests for ``export_reports_impl``."""

from __future__ import annotations

import base64
import csv
import io
import zipfile
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.infra.reports.export import export_reports_impl

pytestmark = pytest.mark.asyncio


class TestExportReportsClient:
    async def test_returns_export_response(
        self, pool, redis_client, profile_identity_factory
    ):
        # The reports export gate now requires attempt:report (EXPORT-GAP fix).
        profile = await profile_identity_factory(
            permissions=[("attempt", "report")],
        )

        result = await export_reports_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        if result.row_count == 0:
            assert result.content == ""
            assert result.file_name == ""
            return

        assert result.file_name.endswith(".zip")
        assert result.mime_type == "application/zip"
        assert result.content != ""
        assert result.row_count > 0


def _acquire_pool() -> MagicMock:
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_full_export_with_runs_and_traces_sources_ids_per_model(monkeypatch):
    """Regression for the #108-class bug (sibling of PR #140).

    The reports full-export id-collection + groups.csv/runs.csv writers used to
    read ``agent_ids``/``prompt_ids``/``instruction_ids``/``tool_ids``/
    ``voice_ids`` off the trace (``g``) and the run (``r``). After the
    runs→traces refactor (#102) traces carry no ``agent_ids`` and runs carry
    none of those fields, so the path raised ``AttributeError`` whenever the
    export had traces+runs. Agents now come from the parent invocation and the
    config bundle from the linked trace.
    """
    import app.infra.reports.export as mod
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
    inv_id = uuid4()
    trace_id = uuid4()
    run_id = uuid4()

    agent_id = uuid4()
    prompt_id = uuid4()
    instruction_id = uuid4()
    tool_id = uuid4()
    voice_id = uuid4()

    invocation = GetTestInvocationResponse(
        invocation_id=inv_id,
        test_id=uuid4(),
        group_id=None,
        invocation_created_at=now,
        invocation_title="inv",
        use_custom=False,
        position=0,
        invocation_completed=False,
        grade_id=None,
        grade_score=None,
        grade_passed=None,
        grade_time_taken=None,
        rubric_id=None,
        agent_ids=[agent_id],
        quality_id=None,
        department_ids=[],
        voice_id=None,
        temperature_level_id=None,
        reasoning_level_id=None,
        modality_ids=[],
    )
    trace = GetTestInvocationTracesResponse(
        id=trace_id,
        test_invocation_id=inv_id,
        run_id=None,
        created_at=now,
        updated_at=now,
        generated=False,
        mcp=False,
        active=True,
        voice_ids=[voice_id],
        prompt_ids=[prompt_id],
        instruction_ids=[instruction_id],
        tool_ids=[tool_id],
    )
    run = GetTestInvocationRunsResponse(
        id=run_id,
        test_invocation_id=inv_id,
        test_invocation_traces_id=trace_id,
        run_id=None,
        created_at=now,
        updated_at=now,
        generated=False,
        mcp=False,
        active=True,
    )

    def _name(nid, label):
        return GetNameResponse(
            id=nid, name=label, created_at=now, active=True, mcp=False,
            generated=False,
        )

    names = [
        _name(agent_id, "AgentName"),
        _name(prompt_id, "PromptName"),
        _name(instruction_id, "InstructionName"),
        _name(tool_id, "ToolName"),
    ]
    voices = [
        GetVoiceResponse(
            id=voice_id, voice="VoiceName", created_at=now, active=True,
            mcp=False, generated=False,
        )
    ]

    monkeypatch.setattr(
        mod,
        "resolve_profile_identity_context",
        AsyncMock(
            return_value=SimpleNamespace(
                role_permissions=[("attempt", "report")],  # holds report perm
                role_level=0,  # superadmin → dept_clamp None (no scope interference)
                department_ids=[],
            )
        ),
    )
    monkeypatch.setattr(
        mod,
        "search_test_invocation_entries_internal",
        AsyncMock(return_value=([invocation], 1)),
    )
    monkeypatch.setattr(
        mod,
        "search_test_invocation_traces",
        AsyncMock(return_value=([trace], 1)),
    )
    monkeypatch.setattr(
        mod, "search_test_invocation_runs", AsyncMock(return_value=([run], 1))
    )
    monkeypatch.setattr(mod, "get_names", AsyncMock(return_value=names))
    monkeypatch.setattr(mod, "get_departments", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "get_voices", AsyncMock(return_value=voices))

    pool, redis = _acquire_pool(), AsyncMock()
    result = await export_reports_impl(pool, redis, profile_id=uuid4())

    assert result.file_name.endswith(".zip")
    assert result.row_count == 3  # 1 invocation + 1 trace + 1 run
    zip_bytes = base64.b64decode(result.content)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        groups_csv = zf.read("groups.csv").decode("utf-8")
        runs_csv = zf.read("runs.csv").decode("utf-8")

    grp_rows = list(csv.reader(io.StringIO(groups_csv)))
    grp = dict(zip(grp_rows[0], grp_rows[1]))
    assert grp["id"] == str(trace_id)
    assert grp["agents"] == "AgentName"  # from parent invocation, not the trace
    assert grp["voices"] == "VoiceName"  # from the trace bundle
    assert grp["prompts"] == "PromptName"
    assert grp["instructions"] == "InstructionName"
    assert grp["tools"] == "ToolName"

    run_rows = list(csv.reader(io.StringIO(runs_csv)))
    rec = dict(zip(run_rows[0], run_rows[1]))
    assert rec["id"] == str(run_id)
    assert rec["agents"] == "AgentName"  # from parent invocation
    assert rec["voices"] == "VoiceName"  # from linked trace
    assert rec["prompts"] == "PromptName"
    assert rec["instructions"] == "InstructionName"
    assert rec["tools"] == "ToolName"


async def test_reports_export_denied_without_report_permission(monkeypatch):
    """EXPORT-GAP: the reports export view requires the same ``attempt:report``
    capability as its on-screen read sibling — NOT the bare ``attempt:export``
    that #404's gate checks. A low-tier caller (GTA/UTA/Guest) who holds
    attempt:export but not attempt:report is denied 403 before any data is read,
    closing the privilege-escalating org-wide grade/report dump."""
    import app.infra.reports.export as mod
    from fastapi import HTTPException

    monkeypatch.setattr(
        mod,
        "resolve_profile_identity_context",
        AsyncMock(
            return_value=SimpleNamespace(
                role_permissions=[("attempt", "export")],  # has export, NOT report
                role_level=4,
                department_ids=[uuid4()],
            )
        ),
    )
    search = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(mod, "search_test_invocation_entries_internal", search)

    with pytest.raises(HTTPException) as exc:
        await export_reports_impl(_acquire_pool(), AsyncMock(), profile_id=uuid4())
    assert exc.value.status_code == 403
    search.assert_not_called()  # denied before any org-wide read


async def test_reports_export_non_super_clamps_to_own_departments(monkeypatch):
    """A permitted non-super actor (has attempt:report) clamps the invocation
    dump to its OWN departments (cross-dept leak fix); superadmin is unconstrained
    (covered by the full-export test above with role_level 0 → None)."""
    import app.infra.reports.export as mod

    my_dept = uuid4()
    captured = {}

    async def _search(conn, redis, **kwargs):
        captured["suite_department_ids"] = kwargs.get("suite_department_ids")
        return ([], 0)

    monkeypatch.setattr(
        mod,
        "resolve_profile_identity_context",
        AsyncMock(
            return_value=SimpleNamespace(
                role_permissions=[("attempt", "report")],
                role_level=2,  # non-super
                department_ids=[my_dept],
            )
        ),
    )
    monkeypatch.setattr(mod, "search_test_invocation_entries_internal", _search)

    await export_reports_impl(_acquire_pool(), AsyncMock(), profile_id=uuid4())
    assert captured["suite_department_ids"] == [my_dept]  # clamped to own dept
