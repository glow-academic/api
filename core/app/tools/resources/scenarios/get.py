"""Scenarios Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenarios.types import GetScenarioResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_scenarios(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetScenarioResponse]:
    """Fetch scenarios_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "scenarios"]
    key = cache_key("/v5/resources/scenarios/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, problem_statement_enabled, objectives_enabled,
               video_enabled, images_enabled, questions_enabled, department_ids,
               persona_ids, parameter_field_ids, document_ids, objective_ids,
               image_ids, video_ids, question_ids, option_ids, problem_statement_ids,
               created_at, active, generated, mcp
        FROM scenarios_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetScenarioResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            problem_statement_enabled=r["problem_statement_enabled"],
            objectives_enabled=r["objectives_enabled"],
            video_enabled=r["video_enabled"],
            images_enabled=r["images_enabled"],
            questions_enabled=r["questions_enabled"],
            department_ids=r["department_ids"] or [],
            persona_ids=r["persona_ids"] or [],
            parameter_field_ids=r["parameter_field_ids"] or [],
            document_ids=r["document_ids"] or [],
            objective_ids=r["objective_ids"] or [],
            image_ids=r["image_ids"] or [],
            video_ids=r["video_ids"] or [],
            question_ids=r["question_ids"] or [],
            option_ids=r["option_ids"] or [],
            problem_statement_ids=r["problem_statement_ids"] or [],
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
