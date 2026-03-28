"""Tests for simulation permission helpers — pure business logic functions."""

from uuid import uuid4

import pytest

from app.infra.simulation.permissions import (
    compute_can_create,
    compute_can_delete,
    compute_can_draft,
    compute_can_duplicate,
    compute_can_edit,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_scenario_show_flags,
    compute_scenarios_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_scenario_flags,
    compute_show_scenarios,
    get_missing_tools,
    has_access,
)

pytestmark = pytest.mark.asyncio


# ---------- has_access ----------


async def test_has_access_superadmin_always():
    assert has_access("superadmin", None, [uuid4()]) is True


async def test_has_access_no_departments_open_to_all():
    assert has_access("member", [uuid4()], None) is True
    assert has_access("member", [uuid4()], []) is True


async def test_has_access_requires_department_overlap():
    shared = uuid4()
    assert has_access("admin", [shared], [shared]) is True
    assert has_access("admin", [uuid4()], [uuid4()]) is False


async def test_has_access_no_user_departments():
    assert has_access("admin", None, [uuid4()]) is False


# ---------- compute_can_edit ----------


async def test_can_edit_admin_no_cohorts():
    assert compute_can_edit("admin", ["dept"], cohort_usage_count=0) is True


async def test_can_edit_instructional_no_cohorts():
    assert compute_can_edit("instructional", ["dept"], cohort_usage_count=0) is True


async def test_can_edit_blocked_by_cohorts():
    assert compute_can_edit("admin", ["dept"], cohort_usage_count=1) is False


async def test_can_edit_default_simulation_needs_superadmin():
    assert compute_can_edit("admin", None, cohort_usage_count=0) is False
    assert compute_can_edit("superadmin", None, cohort_usage_count=0) is True


async def test_can_edit_denied_for_member():
    assert compute_can_edit("member", ["dept"], cohort_usage_count=0) is False


async def test_can_edit_department_subset_check():
    dept1 = uuid4()
    dept2 = uuid4()
    assert (
        compute_can_edit(
            "admin",
            [dept1, dept2],
            cohort_usage_count=0,
            user_department_ids=[dept1],
        )
        is False
    )


# ---------- compute_disabled_reason ----------


async def test_disabled_reason_none_when_allowed():
    result = compute_disabled_reason("admin", ["dept"], cohort_usage_count=0)
    assert result is None


async def test_disabled_reason_default_simulation():
    result = compute_disabled_reason("admin", None, cohort_usage_count=0)
    assert result is not None
    assert "default simulation" in result.lower()


async def test_disabled_reason_cohorts():
    result = compute_disabled_reason("admin", ["dept"], cohort_usage_count=1)
    assert result is not None
    assert "cohorts" in result.lower()


async def test_disabled_reason_department_mismatch():
    dept1 = uuid4()
    dept2 = uuid4()
    result = compute_disabled_reason(
        "admin", [dept1, dept2], cohort_usage_count=0, user_department_ids=[dept1]
    )
    assert result is not None
    assert "departments" in result.lower()


# ---------- compute_can_delete ----------


async def test_can_delete_admin_no_cohorts():
    assert compute_can_delete("admin", ["dept"], cohort_usage_count=0) is True


async def test_can_delete_blocked_by_cohorts():
    assert compute_can_delete("admin", ["dept"], cohort_usage_count=1) is False


async def test_can_delete_default_denied():
    assert compute_can_delete("admin", None, cohort_usage_count=0) is False


# ---------- compute_can_duplicate ----------


async def test_can_duplicate_admin():
    assert compute_can_duplicate("admin") is True


async def test_can_duplicate_instructional():
    assert compute_can_duplicate("instructional") is True


async def test_can_duplicate_denied_for_member():
    assert compute_can_duplicate("member") is False


# ---------- compute_can_create ----------


async def test_can_create_admin_with_departments():
    assert compute_can_create("admin", [str(uuid4())]) is True


async def test_can_create_non_superadmin_no_departments():
    assert compute_can_create("admin", None) is False


async def test_can_create_denied_for_member():
    assert compute_can_create("member", [str(uuid4())]) is False


# ---------- compute_can_draft ----------


async def test_can_draft_admin():
    assert compute_can_draft("admin") is True


async def test_can_draft_instructional():
    assert compute_can_draft("instructional") is True


async def test_can_draft_denied_for_member():
    assert compute_can_draft("member") is False


# ---------- show flags ----------


async def test_show_name_depends_on_tools():
    assert compute_show_name(True) is True
    assert compute_show_name(False) is False
    assert compute_show_name(None) is False


async def test_show_description_always_true():
    assert compute_show_description() is True


async def test_show_flag_always_true():
    assert compute_show_flag() is True


async def test_show_departments_depends_on_count():
    assert compute_show_departments(3) is True
    assert compute_show_departments(0) is False
    assert compute_show_departments(None) is False


async def test_show_scenarios_depends_on_count():
    assert compute_show_scenarios(1) is True
    assert compute_show_scenarios(0) is False
    assert compute_show_scenarios(None) is False


async def test_show_scenario_flags():
    assert compute_show_scenario_flags([uuid4()], 0, 0) is True
    assert compute_show_scenario_flags(None, 1, 0) is True
    assert compute_show_scenario_flags(None, 0, 1) is True
    assert compute_show_scenario_flags(None, 0, 0) is False


# ---------- required flags ----------


async def test_required_flags():
    assert compute_name_required() is True
    assert compute_description_required() is False
    assert compute_flag_required() is False
    assert compute_scenarios_required() is True


# ---------- scenario_show_flags ----------


async def test_scenario_show_flags_defaults():
    result = compute_scenario_show_flags(None, None, None, None, None)
    assert result["show_problem_statement"] is True
    assert result["show_objectives"] is True
    assert result["show_video"] is False
    assert result["show_text"] is True


async def test_scenario_show_flags_video_enabled():
    result = compute_scenario_show_flags(None, None, True, None, None)
    assert result["show_video"] is True
    assert result["show_text"] is False
    assert result["show_audio"] is False


# ---------- get_missing_tools ----------


async def test_get_missing_tools_none_missing():
    result = get_missing_tools(
        names_has_tools=True,
        descriptions_has_tools=True,
        flags_has_tools=True,
        departments_has_tools=True,
        scenarios_has_tools=True,
    )
    assert result == []


async def test_get_missing_tools_all_missing():
    result = get_missing_tools(
        names_has_tools=False,
        descriptions_has_tools=False,
        flags_has_tools=False,
        departments_has_tools=False,
        scenarios_has_tools=False,
    )
    assert len(result) == 5
    assert "names" in result
    assert "scenarios" in result
