"""Tests for cohort permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.cohort.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.cohort.permissions import compute_can_create

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_admin_with_departments_can_edit(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("cohort", "update")],
                cohort_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_superadmin_can_edit_default(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("cohort", "update")],
                cohort_department_ids=None,
            )
            is True
        )

    async def test_member_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=3,
                role_permissions=[],
                cohort_department_ids=[_DEPT],
            )
            is False
        )


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert (
            compute_disabled_reason(
                role_level=1,
                role_permissions=[("cohort", "update")],
                cohort_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is None
        )

    async def test_returns_reason_for_default(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[("cohort", "update")],
            cohort_department_ids=None,
        )
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(
            role_level=3,
            role_permissions=[],
            cohort_department_ids=[_DEPT],
        )
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access(role_level=0, user_department_ids=None, cohort_department_ids=[_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access(role_level=3, user_department_ids=[_DEPT], cohort_department_ids=None) is True

    async def test_overlap_grants_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], cohort_department_ids=[_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], cohort_department_ids=[_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_granted(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("cohort", "delete")],
                cohort_department_ids=[_DEPT],
                usage_count=0,
            )
            is True
        )

    async def test_can_delete_default_cohort_blocked_for_non_superadmin(self):
        # Default cohort (no departments) cannot be deleted by non-superadmin
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("cohort", "delete")],
                cohort_department_ids=None,
                usage_count=0,
            )
            is False
        )

    async def test_owner_in_department_can_delete(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("cohort", "delete")],
                cohort_department_ids=[_DEPT],
                usage_count=0,
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_cross_department_delete_denied(self):
        # Actor in Dept A (_OTHER) must NOT delete a Dept-B (_DEPT) cohort.
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("cohort", "delete")],
                cohort_department_ids=[_DEPT],
                usage_count=0,
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_superadmin_bypasses_department_scope_on_delete(self):
        assert (
            compute_can_delete(
                role_level=0,
                role_permissions=[("cohort", "delete")],
                cohort_department_ids=[_DEPT],
                usage_count=0,
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_can_duplicate_granted(self):
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("cohort", "duplicate")],
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
                role_permissions=[("cohort", "duplicate")],
                cohort_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_cross_department_duplicate_denied(self):
        # Actor in Dept A (_OTHER) must NOT duplicate a Dept-B (_DEPT)
        # cohort they cannot even edit — mirrors compute_can_delete.
        assert (
            compute_can_duplicate(
                role_level=1,
                role_permissions=[("cohort", "duplicate")],
                cohort_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_superadmin_bypasses_department_scope_on_duplicate(self):
        assert (
            compute_can_duplicate(
                role_level=0,
                role_permissions=[("cohort", "duplicate")],
                cohort_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_can_create_with_departments(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[("cohort", "create")],
                department_ids=[_DEPT],
            )
            is True
        )

    async def test_cannot_create_without_department(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[("cohort", "create")],
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
                role_permissions=[("cohort", "draft")],
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
