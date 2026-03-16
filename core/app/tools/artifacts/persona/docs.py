"""Persona artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.persona.create import create_persona
from app.tools.artifacts.persona.delete import delete_personas
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.search import search_personas
from app.tools.artifacts.persona.update import update_persona


async def get_persona_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the persona artifact."""
    artifact_table = await get_table_info(conn, "persona_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="persona",
        type="artifact",
        description=(
            "Personas define character profiles used in scenarios. "
            "Each persona links to resources (names, descriptions, colors, icons, "
            "instructions, departments, examples, flags, parameter_fields, voices) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_persona,
                description="Creates a new persona artifact with optional resource links.",
            ),
            get_operation_info(
                update_persona,
                description="Updates an existing persona's resource links.",
            ),
            get_operation_info(
                get_personas,
                description="Batch retrieves personas by IDs with optional junction data.",
            ),
            get_operation_info(
                search_personas,
                description="Filtered paginated search returning matching persona IDs.",
            ),
            get_operation_info(
                delete_personas,
                description="Deletes personas by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
