"""Profile Personas resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profile_personas.search import (
    search_profile_personas,
)


async def get_profile_personas_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the profile personas resource."""
    resource_table = await get_table_info(conn, "profile_personas_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="profile_personas",
        type="resource",
        description="Profile-persona associations for cohort assignments.",
        tables=tables,
        operations=[
            get_operation_info(
                create_profile_persona,
                description="Creates a new profile personas resource.",
            ),
            get_operation_info(
                get_profile_personas,
                description="Batch retrieves profile personas by IDs.",
            ),
            get_operation_info(
                search_profile_personas,
                description="Filtered paginated search returning matching profile personas.",
            ),
        ],
    )
