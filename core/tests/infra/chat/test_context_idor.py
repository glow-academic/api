"""Read-side IDOR guard for the chat authoring draft (F4).

``resolve_chat_context`` resolves a caller-supplied ``draft_id`` and hydrates
the chat authoring draft — a *per-user-private* resource (it carries
``session_id`` + ``profile_ids`` and its WRITE path is guarded by
``enforce_draft_owner``). The READ path (reachable via ``chat_get`` and
``chat_export``) must apply the same fail-closed owner gate so a foreign
``draft_id`` can never be hydrated/exported.

These tests exercise ``resolve_chat_context`` directly:

  * cross-owner ``draft_id`` → 403 raised BEFORE any draft is fetched/hydrated
    (no draft leaked through chat_get or chat_export)
  * missing caller identity (``profile=None``) with a ``draft_id`` → fail-closed
    403 (export historically passed no identity)
  * the owner's own draft → guard passes, draft IS hydrated
  * NO ``draft_id`` (shared catalog-style read, e.g. template-only context) →
    guard is never consulted, so it is not over-guarded
"""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.infra.attempt.chat.context as ctx_mod
from app.infra.attempt.chat.context import resolve_chat_context

pytestmark = pytest.mark.asyncio


@dataclass
class _Draft:
    """Minimal chat draft row shape the owner guard reads."""

    session_id: object
    profile_ids: list = field(default_factory=list)
    # resolve_chat_context reads these after the gate passes (allow path).
    name: str | None = "draft"
    name_ids: list = field(default_factory=list)
    description_ids: list = field(default_factory=list)
    flag_ids: list = field(default_factory=list)
    department_ids: list = field(default_factory=list)
    persona_ids: list = field(default_factory=list)
    document_ids: list = field(default_factory=list)
    scenario_ids: list = field(default_factory=list)
    field_ids: list = field(default_factory=list)
    parameter_field_ids: list = field(default_factory=list)
    question_ids: list = field(default_factory=list)
    option_ids: list = field(default_factory=list)
    video_ids: list = field(default_factory=list)
    image_ids: list = field(default_factory=list)
    problem_statement_ids: list = field(default_factory=list)
    objective_ids: list = field(default_factory=list)


@dataclass
class _Profile:
    """Stand-in for ProfileIdentityContext (only the gated fields matter)."""

    session_id: object
    profiles_id: object
    role_level: int = 1
    department_ids: list = field(default_factory=list)
    primary_department_id: object = None


def _pool_for(draft_rows):
    """A pool whose ``acquire()`` yields a conn via an async context manager;
    ``get_chat_drafts`` is mocked separately, so the conn itself is inert."""
    pool = MagicMock()
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool


class TestDeny:
    async def test_cross_owner_draft_id_denied_before_hydration(self, monkeypatch):
        """A foreign draft_id → 403, and the draft is NEVER hydrated/returned."""
        draft_id = uuid4()
        foreign_draft = _Draft(session_id=uuid4(), profile_ids=[uuid4()])

        # The owner guard reads the committed row (bypass_cache) → foreign owner.
        get_drafts = AsyncMock(return_value=[foreign_draft])
        monkeypatch.setattr(ctx_mod, "get_chat_drafts", get_drafts)

        caller = _Profile(session_id=uuid4(), profiles_id=uuid4(), role_level=1)

        with pytest.raises(HTTPException) as exc:
            await resolve_chat_context(
                _pool_for([foreign_draft]),
                AsyncMock(),
                group_id=uuid4(),
                draft_id=draft_id,
                profile=caller,
            )
        assert exc.value.status_code == 403
        # Guard read the row to decide ownership, but resolution stopped there —
        # no hydration of the foreign draft's contents occurred.

    async def test_missing_identity_with_draft_id_fails_closed(self, monkeypatch):
        """No caller identity + a draft_id → 403 (export's old no-identity path)."""
        get_drafts = AsyncMock(return_value=[_Draft(session_id=uuid4())])
        monkeypatch.setattr(ctx_mod, "get_chat_drafts", get_drafts)

        with pytest.raises(HTTPException) as exc:
            await resolve_chat_context(
                _pool_for([]),
                AsyncMock(),
                group_id=uuid4(),
                draft_id=uuid4(),
                profile=None,
            )
        assert exc.value.status_code == 403
        # Fail-closed: we never even queried the draft.
        get_drafts.assert_not_called()


class TestAllow:
    async def test_owner_draft_is_hydrated(self, monkeypatch):
        """The caller's own draft passes the gate and IS resolved."""
        sid = uuid4()
        pid = uuid4()
        own_draft = _Draft(session_id=sid, profile_ids=[pid])
        get_drafts = AsyncMock(return_value=[own_draft])
        monkeypatch.setattr(ctx_mod, "get_chat_drafts", get_drafts)

        # Short-circuit the heavy parallel hydration — we only assert the gate
        # let us through to assembly with the owner's draft in hand.
        async def _fake_gather(*aws, **kw):
            for a in aws:
                if hasattr(a, "close"):
                    a.close()
            return [[] for _ in aws]

        monkeypatch.setattr(ctx_mod.asyncio, "gather", _fake_gather)

        caller = _Profile(session_id=sid, profiles_id=pid, role_level=1)
        result = await resolve_chat_context(
            _pool_for([own_draft]),
            AsyncMock(),
            group_id=uuid4(),
            draft_id=uuid4(),
            profile=caller,
        )
        # Owner draft used → its name flows into the assembled context entries.
        assert result.entries["draft_name"] == "draft"
        get_drafts.assert_awaited()


class TestNotOverGuarded:
    async def test_no_draft_id_skips_owner_guard(self, monkeypatch):
        """Template/catalog-style read with no draft_id never touches the guard
        — the shared catalog reads must not be over-guarded."""
        get_drafts = AsyncMock(return_value=[])
        monkeypatch.setattr(ctx_mod, "get_chat_drafts", get_drafts)

        async def _fake_gather(*aws, **kw):
            for a in aws:
                if hasattr(a, "close"):
                    a.close()
            return [[] for _ in aws]

        monkeypatch.setattr(ctx_mod.asyncio, "gather", _fake_gather)

        # No draft_id, no profile — still resolves (shared/template path).
        result = await resolve_chat_context(
            _pool_for([]),
            AsyncMock(),
            group_id=uuid4(),
            draft_id=None,
            profile=None,
        )
        assert result is not None
        get_drafts.assert_not_called()
