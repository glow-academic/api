"""Shared upload-ownership guard for artifact ``*_download`` impls.

Generalizes the SEC2 fix (``provider/call_download.py``) into a single
black-box helper so the whole download class enforces the same contract:

    An artifact download (``call``/``text``/``file``/``audio``/``image``/
    ``video``) resolves a *session-owned* upload by a caller-supplied resource
    id. Without an ownership check, any actor merely holding the role-level
    ``<artifact>:<kind>_download`` permission could download *any* resource
    id's bytes cross-tenant — and that permission is granted to dept-scoped
    Level-1/Level-2 roles, so a dept-A admin/instructor could exfiltrate a
    dept-B session's uploads (incl. provider/tool call receipts carrying
    create/update arguments). That is the R2 read-IDOR class.

The guard mirrors ``provider/call_download``'s logic exactly: the upload's
owning session must belong to the caller's own profile; otherwise we raise
``404`` (not ``403``) so an unauthorized caller cannot probe which resource
ids exist (a denial that is indistinguishable from a missing resource).

Fail-closed: a ``None`` owning ``session_id`` or an unresolved caller profile
denies. Super-admin/global is *not* special-cased here — that matches the SEC2
exemplar's convention (ownership is the gate; the role-level
``has_permission`` check the impls already run stays as defense-in-depth).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import ProfileIdentityContext
from app.tools.entries.sessions.search import search_sessions


async def enforce_upload_owner(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    upload_session_id: UUID | None,
    requester: ProfileIdentityContext | None,
    not_found_detail: str,
) -> None:
    """Assert the caller owns the session that produced an artifact upload.

    Args:
        pool: asyncpg pool (for the caller-session resolution query).
        redis: cache client.
        upload_session_id: the ``session_id`` the resolved upload/resource
            carries (the session that created the bytes). ``None`` denies.
        requester: the caller's resolved identity context. ``None`` denies.
        not_found_detail: the 404 message — should match the impl's existing
            "no upload found" wording so a denied probe is indistinguishable
            from a genuinely missing resource.

    Raises:
        HTTPException(404): when ownership cannot be proven (no owning session,
            no caller profile, or the owning session is not one of the
            caller's). Mirrors ``provider/call_download``'s SEC2 fix.
    """
    owns = False
    if upload_session_id is not None and requester is not None and requester.profiles_id is not None:
        async with pool.acquire() as conn:
            caller_sessions = await search_sessions(
                conn, redis,
                profile_ids=[requester.profiles_id],
                active=None,
                limit=1000,
            )
        owns = any(str(s.id) == str(upload_session_id) for s in caller_sessions)

    if not owns:
        # 404 (not 403): an unauthorized caller must not be able to distinguish
        # "exists but not yours" from "does not exist" — prevents id probing.
        raise HTTPException(status_code=404, detail=not_found_detail)
