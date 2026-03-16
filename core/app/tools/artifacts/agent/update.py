"""Agent artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.agent.types import UpdateAgentResponse

_UNSET: Any = object()

OWNER_COL = "agent_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("agent_names_junction", "names_id", "agent_names_pkey"),
    ("agent_descriptions_junction", "descriptions_id", "agent_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("agent_departments_junction", "departments_id", "agent_departments_pkey"),
    ("agent_models_junction", "models_id", "agent_models_junction_pkey"),
    (
        "agent_reasoning_levels_junction",
        "reasoning_levels_id",
        "agent_reasoning_levels_junction_pkey",
    ),
    (
        "agent_temperature_levels_junction",
        "temperature_levels_id",
        "agent_temperature_levels_junction_pkey",
    ),
    ("agent_tools_junction", "tools_id", "agent_tools_pkey"),
    ("agent_voices_junction", "voices_id", "agent_voices_junction_pkey"),
    ("agent_agents_junction", "agents_id", "agent_agents_junction_pkey"),
]


async def update_agent(
    conn: asyncpg.Connection,
    agent_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateAgentResponse:
    """Update an agent artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE agent_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            agent_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE agent_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            agent_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=agent_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        model_ids,
        reasoning_level_ids,
        temperature_level_ids,
        tool_ids,
        voice_ids,
        agent_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=agent_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="agent_flags_junction",
            owner_col=OWNER_COL,
            owner_id=agent_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="agent_flags_pkey",
            mcp=mcp,
        )

    return UpdateAgentResponse(id=agent_id)
