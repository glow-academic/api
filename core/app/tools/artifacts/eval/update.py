"""Eval artifact UPDATE — tool layer.

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
from app.tools.artifacts.eval.types import UpdateEvalResponse

_UNSET: Any = object()

OWNER_COL = "eval_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("eval_names_junction", "names_id", "eval_names_pkey"),
    ("eval_descriptions_junction", "descriptions_id", "eval_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("eval_departments_junction", "departments_id", "eval_departments_pkey"),
    ("eval_models_junction", "models_id", "eval_models_junction_pkey"),
    ("eval_model_flags_junction", "model_flags_id", "eval_model_flags_junction_pkey"),
    (
        "eval_model_positions_junction",
        "model_positions_id",
        "eval_model_positions_junction_pkey",
    ),
    (
        "eval_model_rubrics_junction",
        "model_rubrics_id",
        "eval_model_rubrics_junction_pkey",
    ),
    ("eval_evals_junction", "evals_id", "eval_evals_junction_pkey"),
]


async def update_eval(
    conn: asyncpg.Connection,
    eval_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    eval_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateEvalResponse:
    """Update an eval artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE eval_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            eval_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE eval_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            eval_id,
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
                owner_id=eval_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        model_ids,
        model_flag_ids,
        model_position_ids,
        model_rubric_ids,
        eval_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=eval_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="eval_flags_junction",
            owner_col=OWNER_COL,
            owner_id=eval_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="eval_flags_pkey",
            mcp=mcp,
        )

    return UpdateEvalResponse(id=eval_id)
