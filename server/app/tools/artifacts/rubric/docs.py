"""Rubric artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.rubric.create import create_rubric
from app.tools.artifacts.rubric.delete import delete_rubrics
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.artifacts.rubric.search import search_rubrics
from app.tools.artifacts.rubric.update import update_rubric


async def get_rubric_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the rubric artifact."""
    artifact_table = await get_table_info(conn, "rubric_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="rubric",
        type="artifact",
        description=(
            "Rubrics define evaluation criteria with scoring standards. "
            "Each rubric links to resources (names, descriptions, departments, points, standard_groups, standards) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_rubric,
                description="Creates a new rubric artifact with optional resource links.",
            ),
            get_operation_info(
                update_rubric,
                description="Updates an existing rubric's resource links.",
            ),
            get_operation_info(
                get_rubrics,
                description="Batch retrieves rubrics by IDs with optional junction data.",
            ),
            get_operation_info(
                search_rubrics,
                description="Filtered paginated search returning matching rubric IDs.",
            ),
            get_operation_info(
                delete_rubrics,
                description="Deletes rubrics by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
