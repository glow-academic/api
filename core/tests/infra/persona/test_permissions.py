"""Tests for persona permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.persona.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.persona.permissions import compute_can_create

pytestmark = pytest.mark.asyncio(loop_scope="session")

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_admin_with_matching_departments_can_edit(self):
        assert compute_can_edit(1, [("persona", "update")], [_DEPT], 0, [_DEPT]) is True

    async def test_superadmin_can_edit_default(self):
        assert compute_can_edit(0, [("persona", "update")], None, 0) is True

    async def test_admin_cannot_edit_default(self):
        assert compute_can_edit(1, [("persona", "update")], None, 0) is False

    async def test_member_cannot_edit(self):
        assert compute_can_edit(3, [], [_DEPT], 0) is False

    async def test_blocked_by_usage(self):
        assert compute_can_edit(1, [("persona", "update")], [_DEPT], 1) is False


class TestComputeDisabledReason:
    async def test_returns_none_when_allowed(self):
        assert compute_disabled_reason(1, [("persona", "update")], [_DEPT], 0, [_DEPT]) is None

    async def test_returns_reason_for_default(self):
        reason = compute_disabled_reason(1, [("persona", "update")], None, 0)
        assert reason is not None
        assert "default" in reason.lower()

    async def test_returns_reason_for_usage(self):
        reason = compute_disabled_reason(1, [("persona", "update")], [_DEPT], 1)
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason(3, [], [_DEPT], 0)
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
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 0) is True

    async def test_can_delete_blocked_by_usage(self):
        assert compute_can_delete(1, [("persona", "delete")], [_DEPT], 1) is False

    async def test_can_duplicate_granted(self):
        assert compute_can_duplicate(1, [("persona", "duplicate")]) is True

    async def test_can_duplicate_denied(self):
        assert compute_can_duplicate(3, []) is False

    async def test_can_create_with_departments(self):
        assert compute_can_create(1, [("persona", "create")], [_DEPT]) is True

    async def test_cannot_create_without_department(self):
        assert compute_can_create(1, [("persona", "create")], None) is False

    async def test_member_cannot_create(self):
        assert compute_can_create(3, [], [_DEPT]) is False

    async def test_can_draft_granted(self):
        assert compute_can_draft(1, [("persona", "draft")]) is True

    async def test_can_draft_denied(self):
        assert compute_can_draft(3, []) is False
