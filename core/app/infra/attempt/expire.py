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
from redis.asyncio import Redis

from app.infra.attempt.complete import complete_attempt_impl
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

GRACE_SECONDS = 60  # 1 minute grace period
CHECK_INTERVAL = 60  # check every 60 seconds


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
            is_completed=False,
            is_archived=False,
            limit=1000,
        )

    for attempt in attempts:
        # 2. Get chats for this attempt
        async with pool.acquire() as conn:
            chats, _ = await search_attempt_chats(
                conn,
                attempt_ids=[attempt.attempt_id],
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
            )
            expired.append({
                "attempt_id": str(attempt.attempt_id),
                "completion_id": result["completion_id"],
            })
            logger.info(f"Expired attempt {attempt.attempt_id}")
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
