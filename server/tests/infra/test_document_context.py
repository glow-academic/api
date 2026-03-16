"""Integration tests for infra.document_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.document.context import resolve_document_context
from app.tools.artifacts.document.create import create_document
from app.tools.artifacts.document.update import update_document

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        document = await create_document(conn)
        await update_document(conn, document.id, active=False)

    result = await resolve_document_context(
        pool,
        redis_client,
        document_id=document.id,
        group_id=uuid4(),
    )

    assert result.active is False
