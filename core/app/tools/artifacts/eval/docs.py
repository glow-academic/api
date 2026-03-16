"""Eval artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.eval.create import create_eval
from app.tools.artifacts.eval.delete import delete_evals
from app.tools.artifacts.eval.get import get_evals
from app.tools.artifacts.eval.search import search_evals
from app.tools.artifacts.eval.update import update_eval


async def get_eval_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the eval artifact."""
    artifact_table = await get_table_info(conn, "eval_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="eval",
        type="artifact",
        description=(
            "Evals define evaluation configurations linking models to rubrics. "
            "Each eval links to resources (names, descriptions, departments, "
            "models, model_flags, model_positions, model_rubrics, rubrics) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_eval,
                description="Creates a new eval artifact with optional resource links.",
            ),
            get_operation_info(
                update_eval, description="Updates an existing eval's resource links."
            ),
            get_operation_info(
                get_evals,
                description="Batch retrieves evals by IDs with optional junction data.",
            ),
            get_operation_info(
                search_evals,
                description="Filtered paginated search returning matching eval IDs.",
            ),
            get_operation_info(
                delete_evals,
                description="Deletes evals by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
