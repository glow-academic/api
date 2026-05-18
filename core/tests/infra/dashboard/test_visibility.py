"""Dashboard visibility scope tests."""

from __future__ import annotations

import pytest

from app.infra.dashboard.visibility import (
    resolve_visible_profile_ids,
    resolve_visible_simulation_scope,
)
from app.infra.profile_identity_context import ProfileIdentityContext
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def test_visible_profile_ids_include_lower_privilege_same_department(
    pool,
    redis_client,
):
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.profiles.create import create_profile
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()
    async with pool.acquire() as conn:
        department = await create_department(
            conn,
            name=f"dashboard-visible-dept-{tag}",
            description="Dashboard visibility test",
            redis=redis_client,
        )
        other_department = await create_department(
            conn,
            name=f"dashboard-hidden-dept-{tag}",
            description="Dashboard visibility test",
            redis=redis_client,
        )
        manager_role = await create_role(
            conn,
            redis_client,
            name=f"Dashboard Manager {tag}",
            description="Visibility manager",
            level=1,
        )
        learner_role = await create_role(
            conn,
            redis_client,
            name=f"Dashboard Learner {tag}",
            description="Visibility learner",
            level=5,
        )
        root_role = await create_role(
            conn,
            redis_client,
            name=f"Dashboard Root {tag}",
            description="Visibility root",
            level=0,
        )
        actor = await create_profile(
            conn,
            redis_client,
            name=f"dashboard-actor-{tag}",
            department_ids=[department.id],
            role_id=manager_role.id,
        )
        visible = await create_profile(
            conn,
            redis_client,
            name=f"dashboard-visible-{tag}",
            department_ids=[department.id],
            role_id=learner_role.id,
        )
        hidden_department = await create_profile(
            conn,
            redis_client,
            name=f"dashboard-hidden-department-{tag}",
            department_ids=[other_department.id],
            role_id=learner_role.id,
        )
        hidden_role = await create_profile(
            conn,
            redis_client,
            name=f"dashboard-hidden-role-{tag}",
            department_ids=[department.id],
            role_id=root_role.id,
        )

    profile = ProfileIdentityContext(
        profiles_id=actor.id,
        name=actor.name or "",
        role=manager_role.name,
        role_name=manager_role.name,
        role_description=manager_role.description,
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=department.id,
        department_ids=[department.id],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=1,
    )

    visible_ids = await resolve_visible_profile_ids(pool, profile)

    assert actor.id in visible_ids
    assert visible.id in visible_ids
    assert hidden_department.id not in visible_ids
    assert hidden_role.id not in visible_ids


async def test_visible_simulation_scope_is_all_active_for_level_zero(
    pool,
    redis_client,
):
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.scenarios.create import create_scenario
    from app.tools.resources.simulations.create import create_simulation

    tag = unique_tag()
    async with pool.acquire() as conn:
        department = await create_department(
            conn,
            name=f"dashboard-sim-dept-{tag}",
            description="Dashboard visibility test",
            redis=redis_client,
        )
        scenario = await create_scenario(
            conn,
            redis_client,
            name=f"dashboard-scenario-{tag}",
            description="Dashboard visibility test",
        )
        simulation = await create_simulation(
            conn,
            redis_client,
            name=f"dashboard-simulation-{tag}",
            description="Dashboard visibility test",
            department_ids=[department.id],
            scenario_ids=[scenario.id],
        )

    profile = ProfileIdentityContext(
        profiles_id=simulation.id,
        name="Root",
        role="Root",
        role_name="Root",
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=None,
        department_ids=[],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=0,
    )

    simulation_ids, scenario_ids = await resolve_visible_simulation_scope(pool, profile)

    assert simulation.id in simulation_ids
    assert scenario.id in scenario_ids
