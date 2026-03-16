"""Setting artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.setting.create import create_setting
from app.tools.artifacts.setting.delete import delete_settings
from app.tools.artifacts.setting.get import get_settings
from app.tools.artifacts.setting.search import search_settings
from app.tools.artifacts.setting.update import update_setting


async def get_setting_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the setting artifact."""
    artifact_table = await get_table_info(conn, "setting_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="setting",
        type="artifact",
        description=(
            "Settings define organization-wide configurations for authentication, branding, "
            "and access control. Each setting links to resources (names, descriptions, "
            "departments, auths, auth_item_keys, auth_item_values, colors, profiles, "
            "provider_keys, systems, thresholds) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_setting,
                description="Creates a new setting artifact with optional resource links.",
            ),
            get_operation_info(
                update_setting,
                description="Updates an existing setting's resource links.",
            ),
            get_operation_info(
                get_settings,
                description="Batch retrieves settings by IDs with optional junction data.",
            ),
            get_operation_info(
                search_settings,
                description="Filtered paginated search returning matching setting IDs.",
            ),
            get_operation_info(
                delete_settings,
                description="Deletes settings by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
