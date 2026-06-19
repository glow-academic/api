"""Tests for attempt permissions — check_attempt_access + score aggregates."""
from uuid import uuid4

import pytest

from app.infra.attempt.permissions import (
    ROLE_HIERARCHY,
    check_attempt_access,
    compute_attempt_aggregates,
    compute_passed_standards,
    compute_percentage,
    compute_total_possible_points,
)
from app.infra.attempt.types import ChatData, GradeData

pytestmark = pytest.mark.asyncio

async def test_access_own_attempt():
    pid = uuid4()
    assert check_attempt_access(attempt_profile_id=pid, request_profile_id=pid) is True

async def test_no_access_none_attempt_profile():
    assert check_attempt_access(attempt_profile_id=None, request_profile_id=uuid4()) is False

async def test_higher_role_gets_access():
    assert check_attempt_access(
        attempt_profile_id=uuid4(), request_profile_id=uuid4(),
        request_role="admin", attempt_role="member",
    ) is True

async def test_role_hierarchy_ordering():
    assert ROLE_HIERARCHY["superadmin"] > ROLE_HIERARCHY["admin"]
    assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["instructional"]
    assert ROLE_HIERARCHY["instructional"] > ROLE_HIERARCHY["member"]


# ── Department scope on check_attempt_access (#152/#148) ─────────────────────
# These pin that the department-overlap decision (department_in_scope), resolved
# by the caller, is ANDed with the role hierarchy for a non-super, non-self
# caller — and that self / super-admin are unaffected by it.


async def test_same_department_higher_role_allowed():
    """(a) SAME-dept: higher role + owner in department scope → allowed."""
    assert check_attempt_access(
        attempt_profile_id=uuid4(),
        request_profile_id=uuid4(),
        request_role="instructional",
        attempt_role="member",
        department_in_scope=True,
    ) is True


async def test_cross_department_higher_role_denied():
    """(b) CROSS-dept (critical): higher role but owner OUT of department scope
    → denied. The role hierarchy alone would have allowed; the dept gate closes
    the cross-department gap."""
    assert check_attempt_access(
        attempt_profile_id=uuid4(),
        request_profile_id=uuid4(),
        request_role="instructional",
        attempt_role="member",
        department_in_scope=False,
    ) is False


async def test_self_allowed_regardless_of_department():
    """(c) SELF: own attempt is allowed even when out of department scope."""
    pid = uuid4()
    assert check_attempt_access(
        attempt_profile_id=pid,
        request_profile_id=pid,
        request_role="member",
        attempt_role="member",
        department_in_scope=False,
    ) is True


async def test_superadmin_allowed_regardless_of_department():
    """(d) SUPER-ADMIN: global access — allowed even when out of department
    scope (the dept gate never applies to super-admins)."""
    assert check_attempt_access(
        attempt_profile_id=uuid4(),
        request_profile_id=uuid4(),
        request_role="superadmin",
        attempt_role="member",
        department_in_scope=False,
    ) is True


def _graded_chat(*, completed: bool, score: float, total_points: float) -> ChatData:
    """Build a minimal ChatData carrying a grade (mirrors get.py attachment)."""
    return ChatData(
        id=uuid4(),
        completed=completed,
        grade=GradeData(
            score=score,
            passed=score >= total_points,
            time_taken=10,
            total_points=total_points,
        ),
    )


def test_pct_not_over_100_for_graded_not_completed_chat():
    """Regression: a graded-but-not-completed chat must not inflate the
    numerator without a matching denominator (pct must stay <= 100).

    The grade pipeline allows grading a chat that was never completed
    (chat_grade is an independent operation from chat_complete — no completion
    guard), so the numerator (compute_attempt_aggregates.total_score) and the
    denominator (compute_total_possible_points) must count the SAME chat set.
    """
    chats = [_graded_chat(completed=False, score=10.0, total_points=10.0)]

    total_score = compute_attempt_aggregates(chats)["total_score"]
    total_possible = compute_total_possible_points(chats)
    pct = compute_percentage(total_score, total_possible)

    # numerator counted the graded chat → denominator must too
    assert total_score == 10.0
    assert total_possible == 10.0
    assert pct == 100.0
    assert pct <= 100.0


def test_pct_aligned_numerator_denominator_mixed():
    """Mixed completed + graded-not-completed chats: pct stays <= 100."""
    chats = [
        _graded_chat(completed=True, score=8.0, total_points=10.0),
        _graded_chat(completed=False, score=10.0, total_points=10.0),
    ]
    total_score = compute_attempt_aggregates(chats)["total_score"]
    total_possible = compute_total_possible_points(chats)
    pct = compute_percentage(total_score, total_possible)

    assert total_score == 18.0
    assert total_possible == 20.0
    assert pct == 90.0
    assert pct <= 100.0


def test_ungraded_chat_contributes_no_points():
    """A chat with no grade contributes to neither numerator nor denominator."""
    chats = [ChatData(id=uuid4(), completed=True, grade=None)]
    assert compute_attempt_aggregates(chats)["total_score"] == 0.0
    assert compute_total_possible_points(chats) == 0.0


def test_pct_clamped_to_100_on_bonus_inflation():
    """B4: a bonus-inflated raw score (score > total) clamps to 100, matching
    the benchmark percent path (benchmark/get.py:_score_percent) — never >100."""
    # 12/10 raw == 120%, must report 100.0 like the benchmark path.
    assert compute_percentage(12.0, 10.0) == 100.0
    assert compute_percentage(12.0, 10.0) <= 100.0
    # Normal sub-100 grade is unaffected.
    assert compute_percentage(7.0, 10.0) == 70.0


# ── compute_passed_standards — pass/fail must use the ACHIEVED standard points,
#    not the standard-group MAX (the feedback's persisted ``total``). Before the
#    fix, group-max >= pass_points made every evaluated standard "passed". ──────


def _passed_setup(achieved_points, pass_points):
    sid = uuid4()
    sg_id = uuid4()
    feedbacks = [{"standard_id": sid, "total": 10.0}]  # total = group MAX (red herring)
    standard_groups_meta = {sg_id: {"pass_points": pass_points}}
    standards_meta = {sid: {"points": achieved_points, "standard_group_id": sg_id}}
    result = compute_passed_standards(feedbacks, standard_groups_meta, standards_meta)
    return result[0]["passed"]


def test_passed_standards_failing_level_is_not_passed():
    # Grader picked a failing rubric level: achieved 2 < pass 7 → NOT passed
    # (regression: was wrongly True because group-max 10 >= 7).
    assert _passed_setup(achieved_points=2, pass_points=7) is False


def test_passed_standards_passing_level_is_passed():
    assert _passed_setup(achieved_points=8, pass_points=7) is True


def test_passed_standards_boundary_is_inclusive():
    # Achieved exactly at threshold → passed (>=).
    assert _passed_setup(achieved_points=7, pass_points=7) is True


def test_passed_standards_no_pass_points_passes_any_achieved():
    # No configured pass_points (0) → any achieved level passes (0 >= 0).
    assert _passed_setup(achieved_points=0, pass_points=0) is True


def test_graded_not_completed_null_time_taken_still_counts_score():
    """F3: a graded-but-not-completed chat with NULL ``time_taken`` and a
    ``created_at`` must still contribute its score to the numerator.

    Previously the active-chat elapsed branch (``created_at and not completed``)
    preempted the score-counting branch, so such a chat's score was dropped from
    ``total_score`` while ``compute_total_possible_points`` still counted its
    ``total_points`` — understating the attempt percentage. The score/passed
    accounting is now decoupled from the elapsed-time branch and gated on the
    same ``grade + total_points`` the denominator uses.
    """
    chat = ChatData(
        id=uuid4(),
        completed=False,  # not completed → would have hit the elapsed branch
        created_at="2026-01-01T00:00:00+00:00",  # truthy → old branch preemption
        grade=GradeData(
            score=8.0, passed=True, time_taken=None, total_points=10.0,
        ),
    )
    total_score = compute_attempt_aggregates([chat])["total_score"]
    total_possible = compute_total_possible_points([chat])
    # Numerator now counts the score (was 0.0 pre-fix); denominator already did.
    assert total_score == 8.0
    assert total_possible == 10.0
    assert compute_percentage(total_score, total_possible) == 80.0


def test_graded_no_rubric_chat_excluded_from_both_numerator_and_denominator():
    """F2: a graded chat with NO rubric (total_points 0/NULL) must count in
    NEITHER total_score nor total_possible — otherwise total_score > total_possible
    and the detail endpoint disagrees with the history path. Aligns the numerator
    with compute_total_possible_points' documented invariant."""
    chats = [
        _graded_chat(completed=True, score=8.0, total_points=10.0),
        # No-rubric grade: score present, total_points 0 (falsy).
        _graded_chat(completed=True, score=5.0, total_points=0.0),
    ]
    total_score = compute_attempt_aggregates(chats)["total_score"]
    total_possible = compute_total_possible_points(chats)
    # Only the rubric chat counts on BOTH sides; the no-rubric 5 is excluded.
    assert total_score == 8.0
    assert total_possible == 10.0
    assert total_score <= total_possible
