"""Regression: eval create/update resolves model-artifact IDs to resource IDs.

Clients (and ``/model/search``) surface *model artifact* IDs, but
``eval_models_junction.models_id`` is FK'd to ``models_resource`` (the
denormalized snapshot each model artifact owns via ``model_models_junction``),
and the eval read side hydrates them back through ``get_models_resource``.
Before the fix ``resolve_eval_values`` passed the artifact IDs straight into the
junction → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.eval.permissions_context import resolve_eval_values
from app.infra.eval.types import CreateEvalItem
from app.tools.artifacts.model.create import create_model as create_model_artifact
from app.tools.resources.models.create import create_model as create_model_resource

pytestmark = pytest.mark.asyncio


async def _seed_model(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_model_resource(
            conn, value=f"m-{uuid4().hex[:8]}", name="eval-model", redis=redis_client
        )
        artifact = await create_model_artifact(conn, model_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_model_artifact_id_to_resource_id(pool, redis_client):
    model_a, model_r = await _seed_model(pool, redis_client)

    item = CreateEvalItem(name="eval-xref", model_ids=[model_a])
    async with pool.acquire() as conn:
        errors = await resolve_eval_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.model_ids == [model_r] and model_a not in item.model_ids


async def test_unknown_eval_model_id_passes_through(pool, redis_client):
    m = uuid4()
    item = CreateEvalItem(name="eval-xref-2", model_ids=[m])
    async with pool.acquire() as conn:
        errors = await resolve_eval_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.model_ids == [m]
