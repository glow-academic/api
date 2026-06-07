"""Regression: department create/update resolves setting artifact IDs to resource IDs.

Clients (and ``/setting/search``) surface setting *artifact* IDs as each row's
``id``, but ``department_settings_junction.settings_id`` is FK'd to
``settings_resource`` (the denormalized snapshot each setting artifact owns via
its own ``setting_settings_junction``). Before the fix
``resolve_department_values`` passed the artifact IDs straight through to the
junction write → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.department.permissions_context import resolve_department_values
from app.infra.department.types import CreateDepartmentItem, UpdateDepartmentItem
from app.tools.artifacts.setting.create import (
    create_setting as create_setting_artifact,
)
from app.tools.resources.settings.create import (
    create_setting as create_setting_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_setting(pool, redis_client) -> tuple:
    """Seed a settings_resource snapshot + a setting artifact linked to it.

    Returns ``(artifact_id, resource_id)`` — two distinct id-spaces.
    """
    async with pool.acquire() as conn:
        resource = await create_setting_resource(
            conn, name=f"s-{uuid4().hex[:8]}", redis=redis_client
        )
        artifact = await create_setting_artifact(conn, setting_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_setting_artifact_ids_on_create(pool, redis_client):
    set_a, set_r = await _seed_setting(pool, redis_client)
    assert set_a != set_r  # the two id-spaces genuinely differ

    item = CreateDepartmentItem(name="dept-xref", settings_ids=[set_a])
    async with pool.acquire() as conn:
        errors = await resolve_department_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    # The artifact ID must be rewritten to its settings_resource snapshot ID
    # before the junction write (FK target = settings_resource).
    assert item.settings_ids == [set_r]
    assert set_a not in item.settings_ids


async def test_resolve_rewrites_setting_artifact_ids_on_update(pool, redis_client):
    set_a, set_r = await _seed_setting(pool, redis_client)

    item = UpdateDepartmentItem(id=uuid4(), settings_ids=[set_a])
    async with pool.acquire() as conn:
        errors = await resolve_department_values(
            conn, redis_client, item, is_create=False
        )

    assert errors == []
    assert item.settings_ids == [set_r]


async def test_unknown_setting_ids_pass_through(pool, redis_client):
    # An already-resolved resource ID (or any unknown id) must pass through
    # unchanged so the FK still validates.
    unknown = uuid4()
    item = CreateDepartmentItem(name="dept-xref-2", settings_ids=[unknown])
    async with pool.acquire() as conn:
        errors = await resolve_department_values(
            conn, redis_client, item, is_create=True
        )

    assert errors == []
    assert item.settings_ids == [unknown]
