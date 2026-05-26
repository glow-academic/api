"""Persona drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.persona_drafts.types import CreatePersonaDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_persona_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    color_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    example_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    icon_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreatePersonaDraftResponse:
    """Create a persona_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false (pending acceptance).
    soft: when True, ALL connections are active=false (overrides pending_ids).
    """
    row = await conn.fetchrow(
        """
        INSERT INTO persona_drafts_entry (id, session_id, active, mcp, generated, name)
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
        raise ValueError("Failed to create persona_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

    connections: list[tuple[str, str, list[UUID]]] = [
        ("persona_drafts_colors_connection", "colors_id", color_ids or []),
        (
            "persona_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "persona_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("persona_drafts_examples_connection", "examples_id", example_ids or []),
        ("persona_drafts_flags_connection", "flags_id", flag_ids or []),
        ("persona_drafts_icons_connection", "icons_id", icon_ids or []),
        (
            "persona_drafts_instructions_connection",
            "instructions_id",
            instruction_ids or [],
        ),
        ("persona_drafts_names_connection", "names_id", name_ids or []),
        (
            "persona_drafts_parameter_fields_connection",
            "parameter_fields_id",
            parameter_field_ids or [],
        ),
        ("persona_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("persona_drafts_voices_connection", "voices_id", voice_ids or []),
    ]

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            # soft=True → all inactive; otherwise check pending_ids per resource
            is_active = False if soft else (rid not in _pending)
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                is_active,
            )

    def _all(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in _pending]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "color_ids": _all(color_ids),
        "department_ids": _all(department_ids),
        "description_ids": _all(description_ids),
        "example_ids": _all(example_ids),
        "flag_ids": _all(flag_ids),
        "icon_ids": _all(icon_ids),
        "instruction_ids": _all(instruction_ids),
        "name_ids": _all(name_ids),
        "parameter_field_ids": _all(parameter_field_ids),
        "profile_ids": _all(profile_ids),
        "voice_ids": _all(voice_ids),
        "pending_color_ids": _pending_only(color_ids),
        "pending_department_ids": _pending_only(department_ids),
        "pending_description_ids": _pending_only(description_ids),
        "pending_example_ids": _pending_only(example_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "pending_icon_ids": _pending_only(icon_ids),
        "pending_instruction_ids": _pending_only(instruction_ids),
        "pending_name_ids": _pending_only(name_ids),
        "pending_parameter_field_ids": _pending_only(parameter_field_ids),
        "pending_voice_ids": _pending_only(voice_ids),
    }
    await write_back_row(
        redis,
        "persona_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreatePersonaDraftResponse(id=draft_id)
