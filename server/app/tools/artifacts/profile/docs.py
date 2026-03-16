"""Profile artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.profile.create import create_profile
from app.tools.artifacts.profile.delete import delete_profiles
from app.tools.artifacts.profile.get import get_profiles
from app.tools.artifacts.profile.search import search_profiles
from app.tools.artifacts.profile.update import update_profile


async def get_profile_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the profile artifact."""
    artifact_table = await get_table_info(conn, "profile_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="profile",
        type="artifact",
        description=(
            "Profiles represent user accounts with roles and department memberships. "
            "Each profile links to resources (names, departments, emails, request_limits, roles) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_profile,
                description="Creates a new profile artifact with optional resource links.",
            ),
            get_operation_info(
                update_profile,
                description="Updates an existing profile's resource links.",
            ),
            get_operation_info(
                get_profiles,
                description="Batch retrieves profiles by IDs with optional junction data.",
            ),
            get_operation_info(
                search_profiles,
                description="Filtered paginated search returning matching profile IDs.",
            ),
            get_operation_info(
                delete_profiles,
                description="Deletes profiles by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
