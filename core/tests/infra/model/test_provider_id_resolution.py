"""Regression: model create/update resolves provider-artifact IDs to resource IDs.

Clients (and ``/provider/search``) surface ``provider_artifact`` IDs, but
``model_providers_junction.providers_id`` references the denormalized
``providers_resource`` snapshot each provider artifact owns via
``provider_providers_junction`` — and the model search hydrates it back through
``get_providers_resource``. ``model_providers_junction`` carries no FK, so
before the fix ``resolve_model_values`` passed the artifact ID straight through
and the junction silently stored the wrong ID: no 500, just a model whose
provider never resolves (a broken link, invisible in the pipeline).

These mutation-verified tests exercise the real DB pool through black-box tools
only (no raw SQL): they create a real ``providers_resource`` snapshot, a real
``provider_artifact`` linked to it, then prove resolution rewrites the artifact
ID to its resource ID before the junction write.
"""

from uuid import uuid4

import pytest

from app.infra.model.permissions_context import resolve_model_values
from app.infra.model.types import CreateModelItem
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.tools.resources.providers.create import (
    create_provider as create_provider_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_provider_artifact_with_resource(pool, redis_client) -> tuple:
    """Create a providers_resource snapshot + a provider_artifact linked to it.

    Returns ``(artifact_id, resource_id)``.
    """
    async with pool.acquire() as conn:
        resource = await create_provider_resource(
            conn,
            name=f"model-prov-{uuid4().hex[:8]}",
            redis=redis_client,
        )
        artifact = await create_provider_artifact(
            conn,
            provider_ids=[resource.id],  # links artifact -> resource snapshot
        )
    return artifact.id, resource.id


async def test_resolve_rewrites_provider_artifact_id_to_resource_id(
    pool, redis_client
):
    artifact_id, resource_id = await _seed_provider_artifact_with_resource(
        pool, redis_client
    )

    item = CreateModelItem(name="prov-fk-model", provider_id=artifact_id)
    async with pool.acquire() as conn:
        errors = await resolve_model_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    # The client-supplied provider artifact ID must be rewritten to the
    # providers_resource ID the model search hydrates against.
    assert item.provider_id == resource_id
    assert item.provider_id != artifact_id


async def test_unknown_provider_id_passes_through(pool, redis_client):
    """A non-artifact ID (e.g. an already-resolved resource ID re-submitted)
    is left untouched."""
    not_an_artifact = uuid4()

    item = CreateModelItem(name="prov-fk-model-2", provider_id=not_an_artifact)
    async with pool.acquire() as conn:
        errors = await resolve_model_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    assert item.provider_id == not_an_artifact
