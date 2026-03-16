"""Eval artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.eval.types import CreateEvalResponse

OWNER_COL = "eval_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("eval_names_junction", "names_id"),
    ("eval_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("eval_departments_junction", "departments_id"),
    ("eval_models_junction", "models_id"),
    ("eval_model_flags_junction", "model_flags_id"),
    ("eval_model_positions_junction", "model_positions_id"),
    ("eval_model_rubrics_junction", "model_rubrics_id"),
    ("eval_evals_junction", "evals_id"),
]


async def create_eval(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    eval_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateEvalResponse:
    """Create an eval artifact with optional junction links."""
    is_active = not soft if active is None else active
    eval_id: UUID = await conn.fetchval(
        """
        INSERT INTO eval_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=eval_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        model_ids,
        model_flag_ids,
        model_position_ids,
        model_rubric_ids,
        eval_ids,
    ]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=eval_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="eval_flags_junction",
            owner_col=OWNER_COL,
            owner_id=eval_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateEvalResponse(id=eval_id)
