"""Regression: parameter create/update resolves field-artifact IDs to resource IDs.

Clients (and ``/field/search``) surface *field artifact* IDs, but
``parameter_fields_junction.fields_id`` is FK'd to ``fields_resource``
(constraint ``parameter_fields_field_resource_id_fkey`` — the denormalized
snapshot each field artifact owns via ``field_fields_junction``), and the
parameter read side hydrates them back through ``get_fields_resource``. Before
the fix ``resolve_parameter_values`` passed the artifact IDs straight into the
junction → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.parameter.permissions_context import resolve_parameter_values
from app.infra.parameter.types import CreateParameterItem
from app.tools.artifacts.field.create import create_field as create_field_artifact
from app.tools.resources.fields.create import create_field as create_field_resource

pytestmark = pytest.mark.asyncio


async def _seed_field(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_field_resource(
            conn, name=f"f-{uuid4().hex[:8]}", redis=redis_client
        )
        artifact = await create_field_artifact(conn, field_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_field_artifact_id_to_resource_id(pool, redis_client):
    field_a, field_r = await _seed_field(pool, redis_client)

    item = CreateParameterItem(name="param-xref", field_ids=[field_a])
    async with pool.acquire() as conn:
        errors = await resolve_parameter_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    assert item.field_ids == [field_r] and field_a not in item.field_ids


async def test_unknown_parameter_field_id_passes_through(pool, redis_client):
    f = uuid4()
    item = CreateParameterItem(name="param-xref-2", field_ids=[f])
    async with pool.acquire() as conn:
        errors = await resolve_parameter_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    assert item.field_ids == [f]
