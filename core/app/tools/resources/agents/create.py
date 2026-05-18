"""Agents CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.agents.get import get_agents
from app.tools.resources.agents.types import GetAgentResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_agent(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    department_ids: list[UUID] | None = None,
    model_id: UUID | None = None,
    prompt_id: UUID | None = None,
    rubric_id: UUID | None = None,
    tool_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    voices: list[str] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetAgentResponse:
    """Create an agent resource (plain INSERT — no unique constraint)."""
    agent_id = await conn.fetchval(
        """
        INSERT INTO agents_resource (
            id,
            name,
            description,
            department_ids,
            model_id,
            prompt_id,
            rubric_id,
            tool_ids,
            instruction_ids,
            voices,
            active,
            mcp,
            generated
        )
        VALUES (
            COALESCE($12, uuidv7()),
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11,
            $11
        )
        RETURNING id
        """,
        name,
        description,
        department_ids or [],
        model_id,
        prompt_id,
        rubric_id,
        tool_ids or [],
        instruction_ids or [],
        voices or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "agents"], redis=redis)
    items = await get_agents(conn, [agent_id], redis, bypass_cache=True)
    return items[0]
