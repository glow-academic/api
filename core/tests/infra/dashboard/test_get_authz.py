"""Authorization regression tests for the dashboard analytics read path (#145).

Verifies that a caller-supplied ``target_profile_id`` is honored only when the
target is inside the actor's ``resolve_visible_profile_ids`` set. Both
directions are proven:

* blocked — a low-privilege actor cannot read a foreign profile's analytics
  (this test demonstrates the IDOR pre-fix and the denial post-fix);
* allowed — self, an instructor's in-scope student, and a superadmin all keep
  working (no legitimate-access regression).

All actors/victims/MV data are built through the black-box create helpers used
elsewhere in the suite; no raw SQL beyond the standard MV refresh.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.infra.dashboard.get import get_dashboard_impl_cached
from app.infra.dashboard.types import DashboardRequest
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def _make_actor(pool, redis_client, *, role_level, department_ids=None):
    """Create a full profile artifact (artifact id + resource id) at a role level.

    Returns ``(artifact_id, profiles_resource_id)``. ``artifact_id`` is what the
    HTTP layer passes as ``profile_id``; ``profiles_resource_id`` is the value a
    caller would put in ``target_profile_id`` and what the MV is keyed on.
    """
    from app.tools.artifacts.profile.create import (
        create_profile as create_profile_artifact,
    )
    from app.tools.resources.names.create import create_name
    from app.tools.resources.profiles.create import (
        create_profile as create_profile_resource,
    )
    from app.tools.resources.roles.create import create_role

    tag = unique_tag()
    async with pool.acquire() as conn:
        name = await create_name(conn, f"actor-{tag}", redis_client)
        role = await create_role(
            conn,
            redis_client,
            name=f"Role {tag}",
            description="authz test role",
            level=role_level,
        )
        resource = await create_profile_resource(
            conn,
            redis_client,
            name=f"profile-resource-{tag}",
            description="authz test profile resource",
            role_id=role.id,
            department_ids=list(department_ids or []),
        )
        artifact = await create_profile_artifact(
            conn,
            name_id=name.id,
            role_ids=[role.id],
            department_ids=list(department_ids or []),
            profile_ids=[resource.id],
            redis=redis_client,
        )
    return artifact.id, resource.id


async def _seed_attempt_chat_for(pool, redis_client, profile_resource_id):
    """Seed a full session->attempt->chat chain owned by ``profile_resource_id``
    and refresh the attempt-chat MV so a profile-scoped search returns rows."""
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_bridge.create import (
        create_attempt_chat_bridge,
    )
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.sessions.create import create_session

    async with pool.acquire() as conn:
        session = await create_session(
            conn, redis_client, profile_id=profile_resource_id
        )
        await create_group(
            conn, redis_client, session_id=session.id, artifact_type="persona"
        )
        persona = await create_persona(conn, redis_client)
        attempt = await create_attempt(
            conn,
            redis_client,
            session_id=session.id,
            user_persona_id=persona.id,
            profiles_id=profile_resource_id,
        )
        chat = await create_chat(conn, redis_client, session_id=session.id)
        ac = await create_attempt_chat(
            conn, redis_client, session_id=session.id, chat_id=chat.id
        )
        await create_attempt_chat_bridge(
            conn,
            redis_client,
            attempt_id=attempt.id,
            attempt_chat_id=ac.id,
            session_id=session.id,
        )
        await refresh_attempt_chat(conn)
    return attempt.id


async def _dashboard_for(pool, *, actor_artifact_id, target_profile_id):
    request = DashboardRequest(target_profile_id=target_profile_id)
    bundle, _hit = await get_dashboard_impl_cached(
        pool,
        request,
        profile_id=actor_artifact_id,
        bypass_cache=True,
    )
    return bundle


async def test_low_role_actor_blocked_from_foreign_target(pool, redis_client):
    """BLOCKED: a low-privilege actor requesting a foreign target is denied.

    Pre-fix this returned the victim's analytics (the IDOR); post-fix it raises
    403 and never reaches the victim-scoped search.
    """
    actor_artifact_id, _actor_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _dashboard_for(
            pool,
            actor_artifact_id=actor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


async def test_self_target_allowed(pool, redis_client):
    """ALLOWED: an actor may always read its own analytics."""
    actor_artifact_id, actor_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, actor_resource_id)

    bundle = await _dashboard_for(
        pool,
        actor_artifact_id=actor_artifact_id,
        target_profile_id=actor_resource_id,
    )
    # Reached the scoped search and returned the actor's own bundle.
    assert bundle is not None
    assert bundle.header_metrics is not None


async def test_instructor_allowed_for_in_scope_student(pool, redis_client):
    """ALLOWED: an instructor may read a student in their visible set.

    Visibility = same department + the student's role level >= the actor's.
    """
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        department = await create_department(
            conn, name=f"authz-dept-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _instructor_resource_id = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[department.id]
    )
    _student_artifact_id, student_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[department.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, student_resource_id)

    bundle = await _dashboard_for(
        pool,
        actor_artifact_id=instructor_artifact_id,
        target_profile_id=student_resource_id,
    )
    assert bundle is not None


async def test_instructor_blocked_for_out_of_scope_student(pool, redis_client):
    """BLOCKED: an instructor cannot read a student in a different department."""
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_a = await create_department(
            conn, name=f"authz-dept-a-{tag}", description="authz", redis=redis_client
        )
        dept_b = await create_department(
            conn, name=f"authz-dept-b-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[dept_a.id]
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_b.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _dashboard_for(
            pool,
            actor_artifact_id=instructor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


async def test_superadmin_allowed_for_any_target(pool, redis_client):
    """ALLOWED: a role_level-0 superadmin may read any profile's analytics."""
    superadmin_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=0
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    bundle = await _dashboard_for(
        pool,
        actor_artifact_id=superadmin_artifact_id,
        target_profile_id=victim_resource_id,
    )
    assert bundle is not None
