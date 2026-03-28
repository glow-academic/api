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
        assert compute_can_edit("superadmin") is True

    async def test_admin_cannot_edit(self):
        assert compute_can_edit("admin") is False

    async def test_member_cannot_edit(self):
        assert compute_can_edit("member") is False


class TestComputeDisabledReason:
    async def test_returns_none_for_superadmin(self):
        assert compute_disabled_reason("superadmin") is None

    async def test_returns_reason_for_admin(self):
        reason = compute_disabled_reason("admin")
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason("admin")
        assert reason is not None


class TestHasAccess:
    async def test_superadmin_always_has_access(self):
        assert has_access("superadmin", None, [_DEPT]) is True

    async def test_no_entity_departments_means_accessible(self):
        assert has_access("member", [_DEPT], None) is True

    async def test_overlap_grants_access(self):
        assert has_access("admin", [_DEPT], [_DEPT]) is True

    async def test_no_overlap_denies_access(self):
        assert has_access("admin", [_DEPT], [_OTHER]) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_superadmin(self):
        assert compute_can_delete("superadmin") is True

    async def test_can_delete_admin_denied(self):
        assert compute_can_delete("admin") is False

    async def test_can_duplicate_granted(self):
        assert compute_can_duplicate("superadmin") is True

    async def test_can_duplicate_denied(self):
        assert compute_can_duplicate("member") is False

    async def test_superadmin_can_create(self):
        assert compute_can_create("superadmin") is True

    async def test_admin_cannot_create(self):
        assert compute_can_create("admin") is False

    async def test_can_draft_granted(self):
        assert compute_can_draft("superadmin") is True

    async def test_can_draft_denied(self):
        assert compute_can_draft("member") is False
