"""Regression: setting create/update resolves auth/provider artifact IDs to resource IDs.

Clients (and ``/auth/search`` / ``/provider/search``) surface *artifact* IDs,
but ``setting_auths_junction.auths_id`` and
``setting_providers_junction.providers_id`` are FK'd to ``auths_resource`` /
``providers_resource`` (the denormalized snapshot each artifact owns via its own
self-junction). Before the fix ``resolve_setting_values`` passed the artifact
IDs straight into the junction → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.setting.permissions_context import resolve_setting_values
from app.infra.setting.types import CreateSettingItem
from app.tools.artifacts.auth.create import create_auth as create_auth_artifact
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.tools.resources.auths.create import create_auth as create_auth_resource
from app.tools.resources.providers.create import (
    create_provider as create_provider_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_auth(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_auth_resource(
            conn, redis_client, name=f"a-{uuid4().hex[:8]}"
        )
        artifact = await create_auth_artifact(conn, auth_ids=[resource.id])
    return artifact.id, resource.id


async def _seed_provider(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_provider_resource(
            conn, name=f"p-{uuid4().hex[:8]}", redis=redis_client
        )
        artifact = await create_provider_artifact(conn, provider_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_auth_provider_artifact_ids(pool, redis_client):
    auth_a, auth_r = await _seed_auth(pool, redis_client)
    prov_a, prov_r = await _seed_provider(pool, redis_client)

    item = CreateSettingItem(
        name="setting-xref",
        auth_ids=[auth_a],
        provider_ids=[prov_a],
    )
    async with pool.acquire() as conn:
        errors = await resolve_setting_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.auth_ids == [auth_r] and auth_a not in item.auth_ids
    assert item.provider_ids == [prov_r] and prov_a not in item.provider_ids


async def test_unknown_setting_cross_artifact_ids_pass_through(pool, redis_client):
    a, p = uuid4(), uuid4()
    item = CreateSettingItem(name="setting-xref-2", auth_ids=[a], provider_ids=[p])
    async with pool.acquire() as conn:
        errors = await resolve_setting_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.auth_ids == [a]
    assert item.provider_ids == [p]
