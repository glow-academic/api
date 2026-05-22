"""attempt_message/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_message.types import GetAttemptMessageResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_message_mv"


async def get_attempt_messages(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptMessageResponse]:
    """Get attempt_message entries by IDs from attempt_message_mv (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptMessageResponse] = {}
    missing_ids: list[UUID] = list(ids)
    if not bypass_cache:
        missing_ids = []
        for cid in ids:
            cached = await read_back_row(redis, "attempt_message", cid)
            if cached is not None:
                payload = {k: v for k, v in cached.items() if k != "id"}
                cached_results[str(cid)] = GetAttemptMessageResponse.model_validate(payload)
            else:
                missing_ids.append(cid)

    mv_results: dict[str, GetAttemptMessageResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT message_id, chat_id, attempt_id, type,
                   created_at, completed, text_id,
                   history_file_path, audios_id
            FROM {MV_NAME}
            WHERE message_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["message_id"])] = GetAttemptMessageResponse(**dict(r))

    out: list[GetAttemptMessageResponse] = []
    for cid in ids:
        key = str(cid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
