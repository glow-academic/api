"""Model drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.model_drafts.types import CreateModelDraftResponse


async def create_model_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    pricing_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    voice_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateModelDraftResponse:
    """Create a model_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO model_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create model_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("model_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "model_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("model_drafts_flags_connection", "flags_id", flag_ids or []),
        ("model_drafts_modalities_connection", "modalities_id", modality_ids or []),
        ("model_drafts_names_connection", "names_id", name_ids or []),
        ("model_drafts_pricing_connection", "pricing_id", pricing_ids or []),
        ("model_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("model_drafts_providers_connection", "providers_id", provider_ids or []),
        ("model_drafts_qualities_connection", "qualities_id", quality_ids or []),
        (
            "model_drafts_reasoning_levels_connection",
            "reasoning_levels_id",
            reasoning_level_ids or [],
        ),
        (
            "model_drafts_temperature_levels_connection",
            "temperature_levels_id",
            temperature_level_ids or [],
        ),
        ("model_drafts_values_connection", "values_id", [value_id] if value_id else []),
        ("model_drafts_voices_connection", "voices_id", voice_ids or []),
    ]

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in _pending),
            )

    return CreateModelDraftResponse(id=draft_id)
