"""Problem Statements resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.problem_statements.search import (
    search_problem_statements,
)


async def get_problem_statements_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the problem statements resource."""
    resource_table = await get_table_info(conn, "problem_statements_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="problem_statements",
        type="resource",
        description="Problem statement text for scenario setups.",
        tables=tables,
        operations=[
            get_operation_info(
                create_problem_statement,
                description="Creates a new problem statements resource.",
            ),
            get_operation_info(
                get_problem_statements,
                description="Batch retrieves problem statements by IDs.",
            ),
            get_operation_info(
                search_problem_statements,
                description="Filtered paginated search returning matching problem statements.",
            ),
        ],
    )
