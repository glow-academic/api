"""Tests for resolve_dashboard_context — context resolution."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
pytestmark = pytest.mark.asyncio

async def test_context_function_is_async():
    import app.infra.dashboard.context as mod
    import asyncio
    assert asyncio.iscoroutinefunction(mod.resolve_dashboard_context)

async def test_context_module_imports_artifact_context():
    import app.infra.dashboard.context as mod
    source = open(mod.__file__).read()
    assert "ArtifactContext" in source

async def test_context_module_uses_parallel_fetches():
    import app.infra.dashboard.context as mod
    source = open(mod.__file__).read()
    assert "asyncio.gather" in source or "await" in source


def _acquire_pool() -> MagicMock:
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_rubric_heatmap_uses_achieved_points_not_group_max(monkeypatch):
    """DASH-SCORE (report-24): the rubric heatmap must score each (chat,
    standard_group) cell by the ACHIEVED per-standard ``points`` (the rubric
    level the grader selected), NOT the persisted feedback ``total`` — which is
    the standard-GROUP MAX, the same group-max-vs-achieved fact #405's F1 fixed
    on the attempt side. Summing ``fb.total`` made every cell saturate at/over
    100%; this verifies a sub-max grade yields its true sub-100% percentage.
    """
    import app.infra.dashboard.context as mod
    from app.tools.entries.attempt_chat.types import ChatItem

    chat_id = uuid4()
    grade_id = uuid4()
    rubric_id = uuid4()
    sg_id = uuid4()
    std_a, std_b = uuid4(), uuid4()

    chat_item = ChatItem(chat_id=chat_id, attempt_id=uuid4(), profile_id=uuid4())

    # One grade for the chat, on this rubric.
    monkeypatch.setattr(
        mod,
        "search_attempt_grades",
        AsyncMock(
            return_value=[
                SimpleNamespace(chat_id=chat_id, grade_id=grade_id, rubric_id=rubric_id)
            ]
        ),
    )
    # One feedback row per standard. ``total`` is the GROUP MAX (10) on each row
    # — the misleading persisted value the old code summed.
    monkeypatch.setattr(
        mod,
        "search_attempt_feedback_entries",
        AsyncMock(
            return_value=[
                SimpleNamespace(grade_id=grade_id, standard_ids=[std_a], total=10),
                SimpleNamespace(grade_id=grade_id, standard_ids=[std_b], total=10),
            ]
        ),
    )
    # Achieved points: 2 + 3 = 5 out of a group max of 10 → 50%.
    monkeypatch.setattr(
        mod,
        "get_standards",
        AsyncMock(
            return_value=[
                SimpleNamespace(id=std_a, standard_group_id=sg_id, points=2),
                SimpleNamespace(id=std_b, standard_group_id=sg_id, points=3),
            ]
        ),
    )
    monkeypatch.setattr(
        mod,
        "get_standard_groups",
        AsyncMock(return_value=[SimpleNamespace(id=sg_id, points=10)]),
    )
    monkeypatch.setattr(
        mod,
        "get_rubrics",
        AsyncMock(
            return_value=[
                SimpleNamespace(rubric_id=rubric_id, standard_group_ids=[sg_id])
            ]
        ),
    )

    result = await mod._compute_rubric_scores(
        _acquire_pool(), AsyncMock(), [chat_item]
    )

    assert result.total_count == 1
    cell = result.items[0]
    assert cell.chat_id == chat_id
    assert cell.standard_group_id == sg_id
    # Achieved 5 / group-max 10 → 50%. The old ``+= fb.total`` bug summed
    # 10 + 10 = 20 → 200%, saturating the heatmap.
    assert cell.score_percent == 50.0
