"""Tests for scenario permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.scenario.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.scenario.permissions import (
    compute_can_create,
    compute_can_assign_departments,
)

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()

# Role levels: superadmin=0, admin=1, member=3
# Permission tuples use ("scenario", "<operation>")


class TestComputeCanEdit:
    async def test_admin_with_matching_departments_can_edit(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("scenario", "update")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_superadmin_can_edit_default(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("scenario", "update")],
                scenario_department_ids=None,
                active_simulation_count=0,
            )
            is True
        )

    async def test_admin_cannot_edit_default(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("scenario", "update")],
                scenario_department_ids=None,
                active_simulation_count=0,
            )
            is False
        )

    async def test_member_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=3,
                role_permissions=[],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
            )
            is False
        )

    async def test_blocked_by_usage(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("scenario", "update")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=1,
            )
            is False
        )


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert (
            compute_disabled_reason(
                role_level=1,
                role_permissions=[("scenario", "update")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
                user_department_ids=[_DEPT],
            )
            is None
        )

    async def test_returns_reason_for_default(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[("scenario", "update")],
            scenario_department_ids=None,
            active_simulation_count=0,
        )
        assert reason is not None
        assert "default" in reason.lower()

    async def test_returns_reason_for_usage(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[("scenario", "update")],
            scenario_department_ids=[_DEPT],
            active_simulation_count=1,
        )
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(
            role_level=3,
            role_permissions=[],
            scenario_department_ids=[_DEPT],
            active_simulation_count=0,
        )
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access(0, None, [_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access(3, [_DEPT], None) is True

    async def test_overlap_grants_access(self):
        assert has_access(1, [_DEPT], [_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access(1, [_DEPT], [_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_granted(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("scenario", "delete")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
            )
            is True
        )

    async def test_can_delete_blocked_by_usage(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("scenario", "delete")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=1,
            )
            is False
        )

    async def test_owner_in_department_can_delete(self):
        # Actor B who DOES belong to the scenario's department may delete.
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("scenario", "delete")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_cross_department_delete_denied(self):
        # Actor in Dept A (_OTHER) must NOT delete a scenario scoped to
        # Dept B (_DEPT) — cross-department BOLA guard, mirrors can_edit.
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("scenario", "delete")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_superadmin_bypasses_department_scope_on_delete(self):
        # Top-level role (level 0) deletes across departments as before.
        assert (
            compute_can_delete(
                role_level=0,
                role_permissions=[("scenario", "delete")],
                scenario_department_ids=[_DEPT],
                active_simulation_count=0,
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_can_duplicate_granted(self):
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("scenario", "duplicate")],
            )
            is True
        )

    async def test_can_duplicate_denied(self):
        assert (
            compute_can_duplicate(
                role_level=3,
                role_permissions=[],
            )
            is False
        )

    async def test_owner_in_department_can_duplicate(self):
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("scenario", "duplicate")],
                scenario_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_cross_department_duplicate_denied(self):
        # Actor in Dept A (_OTHER) must NOT duplicate a Dept-B (_DEPT)
        # scenario they cannot even edit — mirrors compute_can_delete.
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("scenario", "duplicate")],
                scenario_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_superadmin_bypasses_department_scope_on_duplicate(self):
        assert (
            compute_can_duplicate(
                role_level=0,
                role_permissions=[("scenario", "duplicate")],
                scenario_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_can_create_with_departments(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[("scenario", "create")],
                department_ids=[_DEPT],
            )
            is True
        )

    async def test_cannot_create_without_department(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[("scenario", "create")],
                department_ids=None,
            )
            is False
        )

    async def test_member_cannot_create(self):
        assert (
            compute_can_create(
                role_level=3,
                role_permissions=[],
                department_ids=[_DEPT],
            )
            is False
        )

    async def test_can_draft_granted(self):
        assert (
            compute_can_draft(
                role_level=1,
                role_permissions=[("scenario", "draft")],
            )
            is True
        )

    async def test_can_draft_denied(self):
        assert (
            compute_can_draft(
                role_level=3,
                role_permissions=[],
            )
            is False
        )


class TestComputeCanAssignDepartments:
    """Write-side department-assignment BOLA guard (create/update body `department_ids`)."""

    async def test_actor_can_assign_own_department(self):
        # Legit path: actor in Dept A assigns the scenario to Dept A.
        assert (
            compute_can_assign_departments(
                role_level=1,
                target_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_cross_department_assignment_denied(self):
        # Exploit: actor in Dept A (_DEPT) tries to assign the scenario to
        # Dept B (_OTHER) — a department they don't belong to.
        assert (
            compute_can_assign_departments(
                role_level=1,
                target_department_ids=[_OTHER],
                user_department_ids=[_DEPT],
            )
            is False
        )

    async def test_partial_cross_department_assignment_denied(self):
        # Mixing an owned dept with a foreign dept must still be rejected
        # (subset, not intersection).
        assert (
            compute_can_assign_departments(
                role_level=1,
                target_department_ids=[_DEPT, _OTHER],
                user_department_ids=[_DEPT],
            )
            is False
        )

    async def test_superadmin_bypasses_assignment_scope(self):
        # Top-level role (level 0) may assign any department, as with edit/delete.
        assert (
            compute_can_assign_departments(
                role_level=0,
                target_department_ids=[_OTHER],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_empty_target_is_allowed(self):
        # No departments assigned by this write — nothing cross-tenant to scope.
        assert (
            compute_can_assign_departments(
                role_level=1,
                target_department_ids=None,
                user_department_ids=[_DEPT],
            )
            is True
        )
