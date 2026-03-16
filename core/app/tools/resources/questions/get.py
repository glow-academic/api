"""Questions Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.questions.types import GetQuestionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_questions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetQuestionResponse]:
    """Fetch questions_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "questions"]
    key = cache_key("/v5/resources/questions/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetQuestionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, question_text, allow_multiple, time,
               created_at, active, generated, mcp
        FROM questions_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetQuestionResponse(
            id=r["id"],
            question_text=r["question_text"],
            allow_multiple=r["allow_multiple"],
            time=r["time"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
