"""Auto-expire stale attempts — background job.

Runs as an asyncio loop during server lifespan. Finds uncompleted attempts
with chats past their time_limit + 60s grace, and completes them.

Uses only black boxes — no raw SQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.complete import complete_attempt_impl
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.utils.cache.mv_refresh_queue import enqueue_pending
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

GRACE_SECONDS = 60  # 1 minute grace period
CHECK_INTERVAL = 60  # check every 60 seconds

# The exact MVs ``complete_attempt_impl`` refreshes once the completion row is
# written (see ``complete.py``). When the owner profile is unresolvable, the
# profile-scoped permission gate inside that refresh raises *after* the
# completion row has already been persisted, so we enqueue these directly
# (degraded, owner-less) to flip ``attempt_mv.is_completed`` — otherwise the
# stale attempt is re-found every cycle and the loop error-spams forever.
_COMPLETE_REFRESH_TARGETS = ["attempt_completion_mv", "attempt_mv"]


async def expire_stale_attempts(
    pool: asyncpg.Pool,
    redis: Redis,
) -> list[dict]:
    """Find and complete all stale attempts.

    An attempt is stale when any of its chats has:
      elapsed > time_limit + GRACE_SECONDS
    """
    now = datetime.now(timezone.utc)
    expired = []

    # 1. Get all uncompleted, non-archived attempts
    async with pool.acquire() as conn:
        attempts, _ = await search_attempts(
            conn,
            redis, is_completed=False,
            is_archived=False,
            limit=1000,
        )

    for attempt in attempts:
        # 2. Get chats for this attempt
        async with pool.acquire() as conn:
            chats, _ = await search_attempt_chats(
                conn,
                redis, attempt_ids=[attempt.attempt_id],
                limit=100,
            )

        # 3. Check if any chat is past time_limit + grace
        stale = False
        elapsed = 0.0
        for chat in chats:
            if not chat.chat_created_at:
                continue
            created = chat.chat_created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            elapsed = (now - created).total_seconds()
            limit = (chat.time_limit_seconds or 0) + GRACE_SECONDS
            if limit > 0 and elapsed > limit:
                stale = True
                break

        if not stale:
            continue

        # 4. Complete the attempt (idempotent)
        try:
            result = await complete_attempt_impl(
                pool,
                redis,
                profile_id=attempt.profile_id or UUID(int=0),
                session_id=UUID(int=0),
                attempt_id=attempt.attempt_id,
                message=f"Auto-expired after {int(elapsed)}s",
                # Trusted system reaper: skip the per-caller attempt-access gate.
                # That gate denies (403) when the attempt owner is NULL/
                # unresolvable (seed/demo attempts), which fired BEFORE the
                # completion row was written — so the attempt never went
                # terminal and was re-found every CHECK_INTERVAL, spamming the
                # ERROR branch below (the 401 degradation never caught the 403).
                system_action=True,
            )
            expired.append({
                "attempt_id": str(attempt.attempt_id),
                "completion_id": result["completion_id"],
            })
            logger.info(f"Expired attempt {attempt.attempt_id}")
        except HTTPException as e:
            # Graceful degradation for stale attempts whose owner profile is
            # unresolvable (deactivated / identity-stripped "bare-shell"
            # profile). ``complete_attempt_impl`` writes the completion row
            # FIRST, then runs a profile-scoped MV refresh whose permission
            # gate raises 401 "Profile not found" for an unresolvable owner.
            # The attempt is therefore already terminal — only the refresh
            # failed — but the global ``attempt_mv`` never flips, so without
            # this branch the attempt is re-found every CHECK_INTERVAL and the
            # loop logs ERROR forever (~540/hr observed in prod).
            #
            # An unresolvable owner has no profile-scoped views to serve, so we
            # skip the profile gate and enqueue the same MVs directly (the
            # underlying enqueue is global, not profile-scoped). This lands the
            # attempt in its terminal state so it is NOT reprocessed next cycle.
            # Narrow: only the 401 profile-not-found case is degraded; any other
            # HTTPException falls through to the ERROR path below.
            if e.status_code == 401:
                if redis is not None:
                    for target in _COMPLETE_REFRESH_TARGETS:
                        await enqueue_pending(redis, target)
                expired.append({"attempt_id": str(attempt.attempt_id)})
                logger.warning(
                    "Expired attempt %s with unresolvable owner profile %s — "
                    "skipped profile-scoped refresh (no views to serve), "
                    "enqueued MV refresh directly",
                    attempt.attempt_id,
                    attempt.profile_id,
                )
            else:
                logger.error(f"Failed to expire attempt {attempt.attempt_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to expire attempt {attempt.attempt_id}: {e}")

    if expired:
        logger.info(f"Expired {len(expired)} attempt(s)")
    return expired


async def expire_loop(pool: asyncpg.Pool, redis: Redis) -> None:
    """Background loop — runs expire check every CHECK_INTERVAL seconds."""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            await expire_stale_attempts(pool, redis)
        except Exception as e:
            logger.error(f"Expire loop error: {e}")
