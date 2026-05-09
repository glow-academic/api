"""Soft calls CREATE — append a ledger row to soft_calls_entry.

The ledger is INSERT-only. State changes (pending → accepted/rejected)
are recorded as new rows; ``soft_calls_mv`` keeps the latest per
``call_id`` for fast lookups.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.soft_calls.types import CreateSoftCallResponse


async def create_soft_call(
    conn: asyncpg.Connection,
    *,
    call_id: UUID,
    artifact: str,
    operation: str,
    artifact_id: UUID,
    status: str = "pending",
    patch: dict[str, Any] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateSoftCallResponse:
    """Append a soft-call ledger row.

    Status transitions are append-only: write a fresh row each time the
    status changes. The materialized view collapses to the latest row
    per ``call_id``.
    """
    if status not in ("pending", "accepted", "rejected"):
        raise ValueError(f"Invalid status: {status!r}")

    patch_json = json.dumps(patch) if patch is not None else None

    entry_id = await conn.fetchval(
        """
        INSERT INTO soft_calls_entry
            (id, call_id, artifact, operation, status, artifact_id, patch, active, mcp, generated)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6, $7::jsonb, $8, $9, true)
        RETURNING id
        """,
        id,
        call_id,
        artifact,
        operation,
        status,
        artifact_id,
        patch_json,
        not soft,
        mcp,
    )

    if entry_id is None:
        raise ValueError("Failed to create soft_calls_entry row")

    return CreateSoftCallResponse(id=entry_id)
