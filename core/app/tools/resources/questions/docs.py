"""Questions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.questions.create import create_question
from app.tools.resources.questions.get import get_questions
from app.tools.resources.questions.search import search_questions


async def get_questions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the questions resource."""
    resource_table = await get_table_info(conn, "questions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="questions",
        type="resource",
        description="Question text for scenario interactions.",
        tables=tables,
        operations=[
            get_operation_info(
                create_question,
                description="Creates a new questions resource.",
            ),
            get_operation_info(
                get_questions,
                description="Batch retrieves questions by IDs.",
            ),
            get_operation_info(
                search_questions,
                description="Filtered paginated search returning matching questions.",
            ),
        ],
    )
