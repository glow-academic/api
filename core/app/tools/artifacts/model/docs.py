"""Model artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.model.create import create_model
from app.tools.artifacts.model.delete import delete_models
from app.tools.artifacts.model.get import get_models
from app.tools.artifacts.model.search import search_models
from app.tools.artifacts.model.update import update_model


async def get_model_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the model artifact."""
    artifact_table = await get_table_info(conn, "model_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="model",
        type="artifact",
        description=(
            "Models define AI model configurations with provider and capability settings. "
            "Each model links to resources (names, descriptions, departments, modalities, "
            "providers, qualities, reasoning_levels, temperature_levels, values, pricing) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_model,
                description="Creates a new model artifact with optional resource links.",
            ),
            get_operation_info(
                update_model, description="Updates an existing model's resource links."
            ),
            get_operation_info(
                get_models,
                description="Batch retrieves models by IDs with optional junction data.",
            ),
            get_operation_info(
                search_models,
                description="Filtered paginated search returning matching model IDs.",
            ),
            get_operation_info(
                delete_models,
                description="Deletes models by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
