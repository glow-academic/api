"""Setting artifact UPDATE — tool layer.

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
from app.tools.artifacts.setting.types import UpdateSettingResponse

_UNSET: Any = object()

OWNER_COL = "setting_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("setting_names_junction", "names_id", "setting_names_pkey"),
    ("setting_descriptions_junction", "descriptions_id", "setting_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("setting_departments_junction", "departments_id", "setting_departments_pkey"),
    ("setting_auths_junction", "auths_id", "setting_auths_pkey"),
    (
        "setting_auth_item_keys_junction",
        "auth_item_keys_id",
        "setting_auth_item_keys_junction_pkey",
    ),
    (
        "setting_auth_item_values_junction",
        "auth_item_values_id",
        "setting_auth_item_values_junction_pkey",
    ),
    ("setting_colors_junction", "colors_id", "setting_colors_pkey"),
    ("setting_profiles_junction", "profiles_id", "setting_profiles_pkey"),
    (
        "setting_provider_keys_junction",
        "provider_keys_id",
        "setting_provider_keys_junction_pkey",
    ),
    ("setting_systems_junction", "systems_id", "setting_systems_junction_pkey"),
    ("setting_thresholds_junction", "thresholds_id", "setting_thresholds_pkey"),
    ("setting_settings_junction", "settings_id", "setting_settings_junction_pkey"),
]


async def update_setting(
    conn: asyncpg.Connection,
    setting_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    auth_item_key_ids: list[UUID] | None = None,
    auth_item_value_ids: list[UUID] | None = None,
    color_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    threshold_ids: list[UUID] | None = None,
    setting_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateSettingResponse:
    """Update a setting artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE setting_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            setting_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE setting_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            setting_id,
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
                owner_id=setting_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        auth_ids,
        auth_item_key_ids,
        auth_item_value_ids,
        color_ids,
        profile_ids,
        provider_key_ids,
        system_ids,
        threshold_ids,
        setting_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=setting_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="setting_flags_junction",
            owner_col=OWNER_COL,
            owner_id=setting_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="setting_flags_pkey",
            mcp=mcp,
        )

    return UpdateSettingResponse(id=setting_id)
