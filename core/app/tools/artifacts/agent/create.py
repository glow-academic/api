"""Agent artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.agent.types import CreateAgentResponse

OWNER_COL = "agent_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("agent_names_junction", "names_id", "agent_names_pkey"),
    ("agent_descriptions_junction", "descriptions_id", "agent_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("agent_departments_junction", "departments_id", "agent_departments_pkey"),
    ("agent_models_junction", "models_id", "agent_models_junction_pkey"),
    ("agent_reasoning_levels_junction", "reasoning_levels_id", "agent_reasoning_levels_junction_pkey"),
    ("agent_temperature_levels_junction", "temperature_levels_id", "agent_temperature_levels_junction_pkey"),
    ("agent_tools_junction", "tools_id", "agent_tools_pkey"),
    ("agent_voices_junction", "voices_id", "agent_voices_junction_pkey"),
    ("agent_agents_junction", "agents_id", "agent_agents_junction_pkey"),
    ("agent_rubrics_junction", "rubrics_id", "agent_rubrics_pkey"),
]


async def create_agent(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateAgentResponse:
    """Create an agent artifact with optional junction links."""
    is_active = not soft if active is None else active
    agent_id: UUID = await conn.fetchval(
        """
        INSERT INTO agent_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=agent_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        model_ids,
        reasoning_level_ids,
        temperature_level_ids,
        tool_ids,
        voice_ids,
        agent_ids,
        rubric_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=agent_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="agent_flags_junction",
            owner_col=OWNER_COL,
            owner_id=agent_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="agent_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateAgentResponse(id=agent_id)
