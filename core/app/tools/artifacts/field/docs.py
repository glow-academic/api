"""Field artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.field.create import create_field
from app.tools.artifacts.field.delete import delete_fields
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.field.search import search_fields
from app.tools.artifacts.field.update import update_field


async def get_field_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the field artifact."""
    artifact_table = await get_table_info(conn, "field_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="field",
        type="artifact",
        description=(
            "Fields define individual form fields used in parameters. "
            "Each field links to resources (names, descriptions, departments, "
            "conditional_parameters) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_field,
                description="Creates a new field artifact with optional resource links.",
            ),
            get_operation_info(
                update_field, description="Updates an existing field's resource links."
            ),
            get_operation_info(
                get_fields,
                description="Batch retrieves fields by IDs with optional junction data.",
            ),
            get_operation_info(
                search_fields,
                description="Filtered paginated search returning matching field IDs.",
            ),
            get_operation_info(
                delete_fields,
                description="Deletes fields by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
