"""Tests for eval permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.eval.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.eval.permissions import compute_can_create

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_superadmin_can_edit(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("eval", "update")],
            )
            is True
        )

    async def test_admin_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_member_cannot_edit(self):
        assert (
            compute_can_edit(
                role_level=3,
                role_permissions=[],
            )
            is False
        )


class TestComputeDisabledReason:
    async def test_returns_none_for_superadmin(self):
        assert (
            compute_disabled_reason(
                role_level=0,
                role_permissions=[("eval", "update")],
            )
            is None
        )

    async def test_returns_reason_for_admin(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[],
        )
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(
            role_level=1,
            role_permissions=[],
        )
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access(role_level=0, user_department_ids=None, eval_department_ids=[_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access(role_level=3, user_department_ids=[_DEPT], eval_department_ids=None) is True

    async def test_overlap_grants_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], eval_department_ids=[_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access(role_level=1, user_department_ids=[_DEPT], eval_department_ids=[_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_superadmin(self):
        assert (
            compute_can_delete(
                role_level=0,
                role_permissions=[("eval", "delete")],
            )
            is True
        )

    async def test_can_delete_admin_denied(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_can_duplicate_granted(self):
        assert (
            compute_can_duplicate(
                role_level=0,
                role_permissions=[("eval", "duplicate")],
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

    async def test_superadmin_can_create(self):
        assert (
            compute_can_create(
                role_level=0,
                role_permissions=[("eval", "create")],
            )
            is True
        )

    async def test_admin_cannot_create(self):
        assert (
            compute_can_create(
                role_level=1,
                role_permissions=[],
            )
            is False
        )

    async def test_can_draft_granted(self):
        assert (
            compute_can_draft(
                role_level=0,
                role_permissions=[("eval", "draft")],
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


class TestWriteDepartmentScope:
    """BOLA gap: write paths (update/delete) must enforce the same
    department scope ``has_access`` enforces on ``get`` — a Dept-A user
    holding ``eval:update``/``eval:delete`` must not edit/delete a
    Dept-B-only eval they cannot even view.
    """

    # --- compute_can_edit ---------------------------------------------
    async def test_edit_cross_department_denied(self):
        # Has the permission, but belongs only to _OTHER; eval is in _DEPT.
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("eval", "update")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_edit_in_department_allowed(self):
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("eval", "update")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_edit_top_level_bypasses_scope(self):
        assert (
            compute_can_edit(
                role_level=0,
                role_permissions=[("eval", "update")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_edit_no_user_depts_keeps_legacy_permission_only(self):
        # List/get rendering callers omit user_department_ids → unchanged.
        assert (
            compute_can_edit(
                role_level=1,
                role_permissions=[("eval", "update")],
                eval_department_ids=[_DEPT],
            )
            is True
        )

    # --- compute_can_delete -------------------------------------------
    async def test_delete_cross_department_denied(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("eval", "delete")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is False
        )

    async def test_delete_in_department_allowed(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("eval", "delete")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_DEPT],
            )
            is True
        )

    async def test_delete_top_level_bypasses_scope(self):
        assert (
            compute_can_delete(
                role_level=0,
                role_permissions=[("eval", "delete")],
                eval_department_ids=[_DEPT],
                user_department_ids=[_OTHER],
            )
            is True
        )

    async def test_delete_no_user_depts_keeps_legacy_permission_only(self):
        assert (
            compute_can_delete(
                role_level=1,
                role_permissions=[("eval", "delete")],
                eval_department_ids=[_DEPT],
            )
            is True
        )
