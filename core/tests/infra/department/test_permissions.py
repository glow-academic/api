"""Tests for department permission helpers — pure business logic."""

from uuid import uuid4

import pytest

from app.infra.department.permissions import (
    compute_can_edit,
    compute_disabled_reason,
    has_access,
    compute_can_delete,
    compute_can_duplicate,
    compute_can_draft,
)
from app.infra.department.permissions import compute_can_create

pytestmark = pytest.mark.asyncio

_DEPT = uuid4()
_OTHER = uuid4()


class TestComputeCanEdit:
    async def test_superadmin_can_edit(self):
        assert compute_can_edit("superadmin", 0) is True

    async def test_admin_cannot_edit(self):
        assert compute_can_edit("admin", 0) is False

    async def test_member_cannot_edit(self):
        assert compute_can_edit("member", 0) is False


class TestComputeDisabledReason:
    async def test_returns_none_for_superadmin(self):
        assert compute_disabled_reason("superadmin", 0) is None

    async def test_returns_reason_for_admin(self):
        reason = compute_disabled_reason("admin", 0)
        assert reason is not None

    async def test_returns_reason_for_low_role(self):
        reason = compute_disabled_reason("admin", 0)
        assert reason is not None


class TestHasAccess:
    async def test_member_has_access(self):
        assert has_access("member") is True

    async def test_admin_has_access(self):
        assert has_access("admin") is True

    async def test_superadmin_has_access(self):
        assert has_access("superadmin") is True

    async def test_none_denied(self):
        assert has_access(None) is False


class TestCanDeleteDuplicateCreateDraft:
    async def test_can_delete_superadmin(self):
        assert compute_can_delete("superadmin", 0) is True

    async def test_can_delete_blocked_by_usage(self):
        assert compute_can_delete("superadmin", 1) is False

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
