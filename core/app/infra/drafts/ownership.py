"""Shared draft-write ownership guard.

Every ``patch_*_draft_impl`` upserts a draft by a *caller-supplied* id
(``draft_id`` / ``idempotency_key`` / ``input_draft_id``) via a
``create_*_draft`` whose entry write is ``INSERT … ON CONFLICT (id) DO
UPDATE``. The role-only ``compute_can_draft`` / ``has_permission`` gate
that precedes the write only proves the caller *may draft* — it does NOT
prove the caller owns *this* draft. So a holder of the relevant draft
permission who learns another user's ``draft_id`` can overwrite that
draft (a write/clobber IDOR), even though the LIST/READ siblings scope by
``session_id`` / ``profiles_id`` (see e.g.
``setting/drafts.py::list_setting_drafts`` and
``persona_drafts/search.py``).

``enforce_draft_owner`` closes the class with a single fail-closed check
mirroring that read-side scoping:

  * No existing row for the id  → first-write / legitimate upsert → ALLOW.
  * Existing row owned by the caller (its ``session_id`` matches the
    caller's session, or its ``profile_ids`` includes the caller's
    ``profiles_id``) → ALLOW.
  * Existing row owned by someone else → 403, before any write.
  * Super-admin (``role_level == 0``) → ALLOW (existing convention,
    mirrors ``compute_can_draft``/delete/duplicate level-0 bypass).

The check operates on the draft object the impl already fetches (or one
fetched on demand via the family's ``get_*_drafts`` tool), so it composes
with the existing draft-first flow without new SQL.
"""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

SUPER_ADMIN_ROLE_LEVEL = 0


class _OwnedDraft(Protocol):
    """Structural shape the guard needs from any ``Get*DraftResponse``."""

    session_id: UUID
    # ``profile_ids`` is present on most draft families; setting drafts are
    # session-scoped only and omit it. Accessed via ``getattr`` so the guard
    # works uniformly regardless.


def _draft_belongs_to_caller(
    draft: Any,
    *,
    caller_session_id: UUID | None,
    caller_profile_id: UUID | None,
) -> bool:
    """True iff ``draft`` is owned by the caller's session or profile.

    Mirrors the read-side list scoping: ``d.session_id = ANY(session_ids)``
    (every family) plus the ``profiles_id`` clamp where the family carries a
    profiles connection (persona/cohort/…).
    """
    draft_session_id = getattr(draft, "session_id", None)
    if (
        caller_session_id is not None
        and draft_session_id is not None
        and draft_session_id == caller_session_id
    ):
        return True

    draft_profile_ids = getattr(draft, "profile_ids", None) or []
    if caller_profile_id is not None and caller_profile_id in draft_profile_ids:
        return True

    return False


async def enforce_draft_owner(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    draft_id: UUID | None,
    getter: Callable[..., Awaitable[list[Any]]],
    caller_session_id: UUID | None,
    caller_profile_id: UUID | None,
    role_level: int,
    artifact: str,
) -> None:
    """Fail-closed ownership guard for a draft upsert.

    Args:
        conn: live connection (the guard reads the *committed* row,
            ``bypass_cache=True``, so it can't be fooled by a stale cache).
        getter: the family's ``get_*_drafts`` tool
            (``(conn, ids, redis, active=None, bypass_cache=True)``).
        draft_id: the caller-supplied target id about to be upserted. ``None``
            means a brand-new server-minted id → nothing to guard.
        caller_session_id / caller_profile_id: the requester's identity.
        role_level: requester role level (``0`` == super-admin → bypass).
        artifact: artifact name, for the error detail.

    Raises:
        HTTPException 403 if the id already belongs to another owner.
    """
    if draft_id is None:
        # First write with a server-minted id — no pre-existing owner to clash.
        return

    if role_level == SUPER_ADMIN_ROLE_LEVEL:
        # Super-admin bypass, per existing draft/delete/duplicate convention.
        return

    # ``active=None`` so we also catch dormant (soft) drafts the caller would
    # otherwise be able to promote. ``bypass_cache=True`` reads the row of
    # record, not a write-back cache entry. A couple of getters
    # (chat/invocation) only ever return committed+dormant and omit the
    # ``active`` kwarg, so pass it only when the signature accepts it.
    getter_kwargs: dict[str, Any] = {"bypass_cache": True}
    if "active" in inspect.signature(getter).parameters:
        getter_kwargs["active"] = None
    existing = await getter(conn, [draft_id], redis, **getter_kwargs)
    if not existing:
        # No row yet → legitimate first-write / upsert of the caller's own id.
        return

    draft = existing[0]
    if _draft_belongs_to_caller(
        draft,
        caller_session_id=caller_session_id,
        caller_profile_id=caller_profile_id,
    ):
        return

    raise HTTPException(
        status_code=403,
        detail=f"You don't have permission to edit this {artifact} draft.",
    )
