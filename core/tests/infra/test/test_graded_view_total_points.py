"""Regression for the test graded-view ``total_points`` typo (R8).

``test/get.py`` built the graded-view ``GradeData`` with
``total_points=getattr(rubric, "points", None)``. ``rubric`` is a
``GetRubricResponse`` which exposes ``total_points`` (NOT ``points``) — so the
denominator was ALWAYS ``None`` and every test graded-view card lost its score
percent + max (the next line correctly used ``"pass_points"``, confirming the
typo). The attempt + benchmark graded views read ``total_points`` correctly;
only the test detail path was wrong.

DB-free: builds a real ``GetRubricResponse`` and applies the same getattr
expression the impl uses, asserting the rubric's points flow through.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.infra.attempt.types import GradeData
from app.tools.resources.rubrics.types import GetRubricResponse


def _rubric(total_points: int, pass_points: int) -> GetRubricResponse:
    return GetRubricResponse(
        id=uuid4(),
        name="r",
        description="",
        department_ids=[],
        total_points=total_points,
        pass_points=pass_points,
        simulation_rubric=False,
        video_rubric=False,
        standard_group_ids=[],
        created_at=datetime.now(UTC),
        active=True,
        generated=False,
        mcp=False,
    )


def test_get_rubric_response_has_total_points_not_points():
    """The shape the typo missed: ``total_points`` exists, ``points`` does not.

    Pre-fix ``getattr(rubric, "points", None)`` silently returned None; the
    fixed ``getattr(rubric, "total_points", None)`` returns the real max.
    """
    rubric = _rubric(total_points=10, pass_points=6)
    assert getattr(rubric, "total_points", None) == 10
    assert getattr(rubric, "points", None) is None  # the buggy attribute name


def test_graded_view_grade_data_carries_rubric_total_points():
    """Mirror the ``test/get.py`` graded-view construction (R8 fix): the score's
    denominator must be the rubric's ``total_points``, not None."""
    rubric = _rubric(total_points=10, pass_points=6)
    grade = GradeData(
        score=8,
        passed=True,
        time_taken=0,
        # The fixed expression from test/get.py:1008.
        total_points=getattr(rubric, "total_points", None) if rubric else None,
        pass_points=getattr(rubric, "pass_points", None) if rubric else None,
    )
    assert grade.total_points == 10  # pre-fix this was None → no percent/max
    assert grade.pass_points == 6
    # 8/10 = 80% pass — only computable now that the denominator is populated.


def test_graded_view_total_points_none_when_no_rubric():
    """No rubric resolved → total_points stays None (unchanged, fail-soft)."""
    rubric = None
    grade = GradeData(
        score=8,
        total_points=getattr(rubric, "total_points", None) if rubric else None,
        pass_points=getattr(rubric, "pass_points", None) if rubric else None,
    )
    assert grade.total_points is None
