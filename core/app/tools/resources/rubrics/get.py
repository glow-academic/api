"""Rubrics Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.rubrics.types import GetRubricResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_rubrics(
    conn: asyncpg.Connection,
    ids: list[UUID] | None,
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetRubricResponse]:
    """Fetch rubrics_resource entries by IDs, or all rows when ids is None."""
    if ids is not None and not ids:
        return []

    tags = ["resources", "rubrics"]
    key = cache_key(
        "/v5/resources/rubrics/get",
        {"ids": [str(id) for id in ids] if ids is not None else ["__all__"]},
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetRubricResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    if ids is not None:
        rows = await conn.fetch(
            """
            SELECT id, name, description, department_ids, total_points, pass_points,
                   simulation_rubric, video_rubric, standard_group_ids,
                   created_at, active, generated, mcp
            FROM rubrics_resource
            WHERE id = ANY($1)
            ORDER BY array_position($1, id)
        """,
            ids,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, name, description, department_ids, total_points, pass_points,
                   simulation_rubric, video_rubric, standard_group_ids,
                   created_at, active, generated, mcp
            FROM rubrics_resource
            ORDER BY created_at
        """,
        )

    items = [
        GetRubricResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            total_points=r["total_points"],
            pass_points=r["pass_points"],
            simulation_rubric=r["simulation_rubric"],
            video_rubric=r["video_rubric"],
            standard_group_ids=r["standard_group_ids"] or [],
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
