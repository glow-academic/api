"""Invocation drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.invocation_drafts.types import (
    CreateInvocationDraftResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_invocation_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    endpoint_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    pricing_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    voice_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateInvocationDraftResponse:
    """Create an invocation_drafts entry with optional connection table links."""
    row = await conn.fetchrow(
        """
        INSERT INTO invocation_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create invocation_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

    # Connections using `draft_id` as FK column
    draft_fk_connections: list[tuple[str, str, list[UUID]]] = [
        (
            "invocation_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "invocation_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("invocation_drafts_flags_connection", "flags_id", flag_ids or []),
        ("invocation_drafts_keys_connection", "keys_id", key_ids or []),
        ("invocation_drafts_names_connection", "names_id", name_ids or []),
        ("invocation_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "invocation_drafts_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "invocation_drafts_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("invocation_drafts_voices_connection", "voices_id", voice_ids or []),
        ("invocation_drafts_modalities_connection", "modalities_id", modality_ids or []),
        ("invocation_drafts_qualities_connection", "qualities_id", quality_ids or []),
        ("invocation_drafts_model_flags_connection", "model_flags_id", model_flag_ids or []),
        ("invocation_drafts_model_positions_connection", "model_positions_id", model_position_ids or []),
        ("invocation_drafts_model_rubrics_connection", "model_rubrics_id", model_rubric_ids or []),
    ]

    pending = pending_ids or set()
    for table, col, ids in draft_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in pending),
            )

    # Connections using `invocation_drafts_id` as FK column
    invocation_fk_connections: list[tuple[str, str, list[UUID]]] = [
        (
            "invocation_drafts_endpoints_connection",
            "endpoints_id",
            endpoint_ids or [],
        ),
        (
            "invocation_drafts_pricing_connection",
            "pricing_id",
            pricing_ids or [],
        ),
        (
            "invocation_drafts_values_connection",
            "values_id",
            [value_id] if value_id else [],
        ),
    ]

    for table, col, ids in invocation_fk_connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (invocation_drafts_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (invocation_drafts_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in pending),
            )

    def _all(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in pending]

    value_ids_for_cache: list[UUID] = [value_id] if value_id else []
    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _all(department_ids),
        "description_ids": _all(description_ids),
        "flag_ids": _all(flag_ids),
        "key_ids": _all(key_ids),
        "modality_ids": _all(modality_ids),
        "quality_ids": _all(quality_ids),
        "model_flag_ids": _all(model_flag_ids),
        "model_position_ids": _all(model_position_ids),
        "model_rubric_ids": _all(model_rubric_ids),
        "name_ids": _all(name_ids),
        "profile_ids": _all(profile_ids),
        "reasoning_level_ids": _all(reasoning_level_ids),
        "temperature_level_ids": _all(temperature_level_ids),
        "voice_ids": _all(voice_ids),
        "value_id": str(value_id) if value_id else None,
        "pricing_ids": _all(pricing_ids),
        "endpoint_ids": _all(endpoint_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_key_ids": _pending_only(key_ids),
        "pending_modality_ids": _pending_only(modality_ids),
        "pending_quality_ids": _pending_only(quality_ids),
        "pending_model_flag_ids": _pending_only(model_flag_ids),
        "pending_model_position_ids": _pending_only(model_position_ids),
        "pending_model_rubric_ids": _pending_only(model_rubric_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_reasoning_level_ids": _pending_only(reasoning_level_ids),
        "pending_temperature_level_ids": _pending_only(temperature_level_ids),
        "pending_voice_ids": _pending_only(voice_ids),
        "pending_value_ids": _pending_only(value_ids_for_cache),
        "pending_pricing_ids": _pending_only(pricing_ids),
        "pending_endpoint_ids": _pending_only(endpoint_ids),
    }
    await write_back_row(
        redis,
        "invocation_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateInvocationDraftResponse(id=draft_id)
