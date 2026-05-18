"""Test draft logic — thin wrapper over invocation draft.

Mirrors the chat / invocation draft pattern: the LLM's `Test_Draft`
tool saves panel state on the benchmark `invocation_entry` (the
template the user is materializing from). The actual draft row
lives in `invocation_drafts_entry` — drafting a "test" really means
drafting the underlying invocation template, so this delegates to
``patch_invocation_draft_impl``.

Auto-discovery picks this up as ``("test", "draft")`` for the
operation registry, mirroring how attempt/draft would work.
"""

from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from app.infra.invocation.draft import patch_invocation_draft_impl
from app.infra.invocation.types import (
    PatchInvocationDraftApiRequest,
    PatchInvocationDraftApiResponse,
)


async def patch_test_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id,
    session_id,
    request: PatchInvocationDraftApiRequest,
) -> PatchInvocationDraftApiResponse:
    """Save draft state for a test invocation template — delegates to invocation draft."""
    return await patch_invocation_draft_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        request=request,
    )


__all__ = ["patch_test_draft_impl"]
