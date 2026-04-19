"""Auto-expire stale attempt chats.

Finds chats past their time_limit + grace_period and completes the attempt.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

import asyncpg

from app.infra.attempt.complete import complete_attempt_impl
from app.infra.globals import get_pool, get_redis_client

logger = logging.getLogger(__name__)

GRACE_PERIOD_MINUTES = int(os.getenv("GRACE_PERIOD_MINUTES", "60"))


async def expire_stale_attempts() -> list[dict[str, Any]]:
    """Find and complete all expired attempts.

    An attempt is expired when any of its chats exceed:
      - Has time_limit: elapsed > time_limit + grace_period
      - No time_limit (infinite): elapsed > grace_period

    Returns list of expired attempt info dicts.
    """
    pool = get_pool()
    redis = get_redis_client()
    if not pool:
        logger.warning("No database pool — skipping expiry check")
        return []

    # Find active chats that are past their effective end time
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (acb.attempt_id)
                acb.attempt_id,
                ace.id AS chat_entry_id,
                ace.chat_id,
                ace.time_limit,
                ace.created_at,
                EXTRACT(EPOCH FROM (NOW() - ace.created_at))::int AS elapsed_seconds,
                (
                    SELECT ap.profile_id
                    FROM attempt_profile_bridge_entry ap
                    WHERE ap.attempt_id = acb.attempt_id AND ap.active = true
                    LIMIT 1
                ) AS profile_id,
                (
                    SELECT s.id
                    FROM session_entry s
                    JOIN session_profile_bridge_entry sp ON sp.session_id = s.id
                    JOIN attempt_profile_bridge_entry ap ON ap.profile_id = sp.profile_id
                    WHERE ap.attempt_id = acb.attempt_id AND s.active = true
                    ORDER BY s.created_at DESC
                    LIMIT 1
                ) AS session_id
            FROM attempt_chat_bridge_entry acb
            JOIN attempt_chat_entry ace ON acb.attempt_chat_id = ace.chat_id
            LEFT JOIN attempt_completion_entry acomp ON acomp.attempt_id = acb.attempt_id
            WHERE acb.active = true
              AND ace.active = true
              AND acomp.id IS NULL
              AND ace.created_at + (
                  COALESCE(NULLIF(ace.time_limit, 0), 0) * interval '1 second'
                  + $1 * interval '1 minute'
              ) < NOW()
            ORDER BY acb.attempt_id, ace.created_at
            """,
            GRACE_PERIOD_MINUTES,
        )

    if not rows:
        return []

    expired = []

    for row in rows:
        attempt_id = UUID(str(row["attempt_id"]))
        profile_id = UUID(str(row["profile_id"])) if row["profile_id"] else None
        session_id = UUID(str(row["session_id"])) if row["session_id"] else None
        elapsed = row["elapsed_seconds"]
        time_limit = row["time_limit"] or 0

        if not profile_id or not session_id:
            logger.warning(
                f"Cannot expire attempt {attempt_id} — missing profile_id or session_id"
            )
            continue

        logger.info(
            f"Expiring attempt {attempt_id} "
            f"(elapsed={elapsed}s, time_limit={time_limit}s, "
            f"grace={GRACE_PERIOD_MINUTES}m)"
        )

        try:
            result = await complete_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                attempt_id=attempt_id,
                message=f"Auto-expired after {elapsed}s",
            )
            expired.append({
                "attempt_id": str(attempt_id),
                "completion_id": result["completion_id"],
                "elapsed_seconds": elapsed,
            })
        except Exception as e:
            logger.error(f"Failed to expire attempt {attempt_id}: {e}")

    logger.info(f"Expired {len(expired)} attempt(s)")
    return expired
