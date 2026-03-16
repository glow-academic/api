"""Agents Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.agents.types import GetAgentResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_agents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetAgentResponse]:
    """Fetch agents_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "agents"]
    key = cache_key("/v5/resources/agents/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetAgentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, department_ids,
               temperature, reasoning, quality,
               model_id, prompt_id, rubric_id, tool_ids, instruction_ids,
               voices, created_at, active, mcp, generated
        FROM agents_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetAgentResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            temperature=r["temperature"],
            reasoning=r["reasoning"],
            quality=r["quality"],
            model_id=r["model_id"],
            prompt_id=r["prompt_id"],
            rubric_id=r["rubric_id"],
            tool_ids=r["tool_ids"] or [],
            instruction_ids=r["instruction_ids"] or [],
            voices=r["voices"] or [],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
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
