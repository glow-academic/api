"""Auth artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.auth.create import create_auth
from app.tools.artifacts.auth.delete import delete_auths
from app.tools.artifacts.auth.get import get_auths
from app.tools.artifacts.auth.search import search_auths
from app.tools.artifacts.auth.update import update_auth


async def get_auth_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the auth artifact."""
    artifact_table = await get_table_info(conn, "auth_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="auth",
        type="artifact",
        description=(
            "Auth artifacts define authentication configurations. "
            "Each auth links to resources (names, descriptions, slugs, departments, "
            "items, protocols) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_auth,
                description="Creates a new auth artifact with optional resource links.",
            ),
            get_operation_info(
                update_auth,
                description="Updates an existing auth's resource links.",
            ),
            get_operation_info(
                get_auths,
                description="Batch retrieves auths by IDs with optional junction data.",
            ),
            get_operation_info(
                search_auths,
                description="Filtered paginated search returning matching auth IDs.",
            ),
            get_operation_info(
                delete_auths,
                description="Deletes auths by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
