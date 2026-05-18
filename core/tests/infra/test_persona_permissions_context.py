"""Integration tests for infra.persona_permissions_context."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.infra.persona.permissions_context import resolve_persona_permissions_context
from app.tools.artifacts.persona.create import create_persona
from app.tools.artifacts.scenario.create import create_scenario
from app.tools.resources.departments.create import create_department
from app.tools.resources.names.create import create_name
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)

pytestmark = pytest.mark.asyncio


async def _create_persona_fixture(
    pool,
    redis_client,
    *,
    with_department: bool = True,
    with_persona_resource: bool = True,
):
    tag = unique_tag()

    async with pool.acquire() as conn:
        name = await create_name(conn, f"persona-{tag}", redis_client)

        department_ids = None
        if with_department:
            department = await create_department(
                conn,
                name=f"department-{tag}",
                description="Persona permissions test department",
                redis=redis_client,
            )
            department_ids = [department.id]

        persona_ids = None
        if with_persona_resource:
            persona_resource = await create_persona_resource(
                conn,
                redis_client,
                name=f"persona-resource-{tag}",
                description="Persona permissions test resource",
                department_ids=department_ids or [],
            )
            persona_ids = [persona_resource.id]
        else:
            persona_resource = None

        artifact = await create_persona(
            conn,
            name_id=name.id,
            department_ids=department_ids,
            persona_ids=persona_ids,
        )

    return artifact, department_ids or [], persona_resource


class TestResolvePersonaPermissionsContext:
    async def test_not_found(self, pool):
        result = await resolve_persona_permissions_context(pool, nonexistent_id())

        assert result.exists is False
        assert result.department_ids == []
        assert result.active_scenario_count == 0

    async def test_exists_with_departments(self, pool, redis_client):
        artifact, department_ids, _persona_resource = await _create_persona_fixture(
            pool, redis_client
        )

        result = await resolve_persona_permissions_context(pool, artifact.id)

        assert result.exists is True
        assert result.department_ids == department_ids
        assert result.active_scenario_count == 0

    async def test_active_scenarios_counted(self, pool, redis_client):
        artifact, department_ids, persona_resource = await _create_persona_fixture(
            pool, redis_client
        )
        assert persona_resource is not None

        async with pool.acquire() as conn:
            scenario_name = await create_name(
                conn, f"scenario-{unique_tag()}", redis_client
            )
            await create_scenario(
                conn,
                name_id=scenario_name.id,
                department_ids=department_ids,
                persona_ids=[persona_resource.id],
            )

        result = await resolve_persona_permissions_context(pool, artifact.id)

        assert result.exists is True
        assert result.department_ids == department_ids
        assert result.active_scenario_count == 1

    async def test_no_personas_resource_skips_scenario_search(self, pool, redis_client):
        artifact, department_ids, persona_resource = await _create_persona_fixture(
            pool,
            redis_client,
            with_persona_resource=False,
        )

        assert persona_resource is None

        result = await resolve_persona_permissions_context(pool, artifact.id)

        assert result.exists is True
        assert result.department_ids == department_ids
        assert result.active_scenario_count == 0

    async def test_no_departments_returns_empty_list(self, pool, redis_client):
        artifact, department_ids, _persona_resource = await _create_persona_fixture(
            pool,
            redis_client,
            with_department=False,
        )

        result = await resolve_persona_permissions_context(pool, artifact.id)

        assert department_ids == []
        assert result.exists is True
        assert result.department_ids == []
        assert result.active_scenario_count == 0
