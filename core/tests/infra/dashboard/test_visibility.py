"""Dashboard visibility scope tests."""

from __future__ import annotations

import pytest

from uuid import uuid4

from app.infra.dashboard.visibility import (
    department_scope_allows,
    is_profile_in_department_scope,
    resolve_visible_profile_ids,
    resolve_visible_simulation_scope,
)
from app.infra.profile_identity_context import ProfileIdentityContext
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


# ── department_scope_allows — pure dept-overlap predicate (#152/#148) ─────────
# The canonical predicate shared by the dashboard/leaderboard bulk scopes and
# the per-resource attempt/emulation gates.


def test_dept_scope_super_admin_is_global():
    """SUPER-ADMIN (role_level 0) sees everyone, even disjoint departments."""
    assert department_scope_allows(
        caller_role_level=0,
        caller_department_ids=[uuid4()],
        owner_role_level=1,
        owner_department_ids=[uuid4()],
    ) is True


def test_dept_scope_overlap_allowed():
    """SAME-dept: a shared department → allowed."""
    shared = uuid4()
    assert department_scope_allows(
        caller_role_level=2,
        caller_department_ids=[shared, uuid4()],
        owner_role_level=5,
        owner_department_ids=[shared],
    ) is True


def test_dept_scope_disjoint_denied():
    """CROSS-dept (critical): no shared department → denied."""
    assert department_scope_allows(
        caller_role_level=2,
        caller_department_ids=[uuid4()],
        owner_role_level=5,
        owner_department_ids=[uuid4()],
    ) is False


def test_dept_scope_global_owner_allowed():
    """GLOBAL owner (no department restriction) is visible to everyone."""
    assert department_scope_allows(
        caller_role_level=2,
        caller_department_ids=[uuid4()],
        owner_role_level=5,
        owner_department_ids=[],
    ) is True


def test_dept_scope_roleless_owner_allowed():
    """ROLELESS owner (shared/system identity) is never hidden."""
    assert department_scope_allows(
        caller_role_level=2,
        caller_department_ids=[uuid4()],
        owner_role_level=None,
        owner_department_ids=[uuid4()],
    ) is True


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


async def test_is_profile_in_department_scope_matrix(pool, redis_client):
    """DB-backed sibling of the dashboard bulk scope: a single owner profile is
    resolved from ``profiles_resource`` and run through the dept-overlap
    predicate. Covers same-dept / cross-dept / global / roleless / super /
    missing — the boundary the attempt read+media gate now enforces."""
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.profiles.create import create_profile
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_a = await create_department(
            conn, name=f"scope-dept-a-{tag}", description="x", redis=redis_client
        )
        dept_b = await create_department(
            conn, name=f"scope-dept-b-{tag}", description="x", redis=redis_client
        )
        learner_role = await create_role(
            conn, redis_client, name=f"Scope Learner {tag}", description="x", level=5
        )
        # Owners in dept A (same dept as caller), dept B (cross), global, roleless.
        same_dept_owner = await create_profile(
            conn, redis_client, name=f"same-{tag}",
            department_ids=[dept_a.id], role_id=learner_role.id,
        )
        cross_dept_owner = await create_profile(
            conn, redis_client, name=f"cross-{tag}",
            department_ids=[dept_b.id], role_id=learner_role.id,
        )
        global_owner = await create_profile(
            conn, redis_client, name=f"global-{tag}",
            department_ids=[], role_id=learner_role.id,
        )
        roleless_owner = await create_profile(
            conn, redis_client, name=f"roleless-{tag}",
            department_ids=[dept_b.id], role_id=None,
        )

    caller = ProfileIdentityContext(
        profiles_id=uuid4(),
        name="caller",
        role="Instructional Staff",
        role_name="Instructional Staff",
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=dept_a.id,
        department_ids=[dept_a.id],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=2,
    )

    # (a) SAME-dept → allowed
    assert await is_profile_in_department_scope(pool, caller, same_dept_owner.id) is True
    # (b) CROSS-dept → denied (critical)
    assert await is_profile_in_department_scope(pool, caller, cross_dept_owner.id) is False
    # (e) GLOBAL owner → allowed
    assert await is_profile_in_department_scope(pool, caller, global_owner.id) is True
    # (e) ROLELESS owner → allowed
    assert await is_profile_in_department_scope(pool, caller, roleless_owner.id) is True
    # Missing owner row → fail closed
    assert await is_profile_in_department_scope(pool, caller, uuid4()) is False

    # (d) SUPER-ADMIN caller → global, even for a cross-department owner
    super_caller = ProfileIdentityContext(
        profiles_id=uuid4(),
        name="super",
        role="Super Administrator",
        role_name="Super Administrator",
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
    assert await is_profile_in_department_scope(pool, super_caller, cross_dept_owner.id) is True
