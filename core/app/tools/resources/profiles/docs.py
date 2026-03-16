"""Profiles resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.search import search_profiles


async def get_profiles_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the profiles resource."""
    resource_table = await get_table_info(conn, "profiles_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="profiles",
        type="resource",
        description="Profile reference IDs linking to profile artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_profile,
                description="Creates a new profiles resource.",
            ),
            get_operation_info(
                get_profiles,
                description="Batch retrieves profiles by IDs.",
            ),
            get_operation_info(
                search_profiles,
                description="Filtered paginated search returning matching profiles.",
            ),
        ],
    )
