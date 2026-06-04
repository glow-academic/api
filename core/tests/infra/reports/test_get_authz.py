"""Authorization regression tests for the reports analytics read path (#145).

Reports had no scoping of its own — any authenticated caller could read any
profile's analytics by supplying ``target_profile_id``. The fix applies the
canonical ``resolve_visible_profile_ids`` policy. Both directions are proven:

* blocked — a low-privilege actor / an out-of-scope instructor is denied
  (demonstrates the IDOR pre-fix, the 403 denial post-fix);
* allowed — self, an in-scope student (instructor), and a superadmin all keep
  working.

Actors/victims/MV data are built via the black-box create helpers; no raw SQL
beyond the standard MV refresh.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.infra.globals import get_redis_client
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


async def _make_actor(pool, redis_client, *, role_level, department_ids=None):
    """Create a full profile artifact; return ``(artifact_id, resource_id)``."""
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
    """Seed a session->attempt->chat chain owned by ``profile_resource_id`` and
    refresh the attempt-chat MV so a profile-scoped search returns the row."""
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


async def _reports_for(pool, *, actor_artifact_id, target_profile_id):
    request = ReportsRequest(target_profile_id=target_profile_id)
    return await get_reports_impl(
        pool,
        get_redis_client(),
        profile_id=actor_artifact_id,
        request=request,
        bypass_cache=True,
    )


async def test_low_role_actor_blocked_from_foreign_target(pool, redis_client):
    """BLOCKED: low-privilege actor requesting a foreign target is denied.

    Pre-fix the victim's report came back (the IDOR); post-fix it is a 403 and
    the victim-scoped search is never issued.
    """
    actor_artifact_id, _ = await _make_actor(pool, redis_client, role_level=99)
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _reports_for(
            pool,
            actor_artifact_id=actor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


async def test_self_target_allowed(pool, redis_client):
    """ALLOWED: an actor may read its own report — and only its own data."""
    actor_artifact_id, actor_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, actor_resource_id)

    response = await _reports_for(
        pool,
        actor_artifact_id=actor_artifact_id,
        target_profile_id=actor_resource_id,
    )
    # Only the actor's own profile resource is present in the hydrated report.
    assert set(response.resources.profiles) <= {str(actor_resource_id)}


async def test_instructor_allowed_for_in_scope_student(pool, redis_client):
    """ALLOWED: an instructor may read an in-scope student's report."""
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        department = await create_department(
            conn, name=f"authz-rpt-dept-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[department.id]
    )
    _student_artifact_id, student_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[department.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, student_resource_id)

    response = await _reports_for(
        pool,
        actor_artifact_id=instructor_artifact_id,
        target_profile_id=student_resource_id,
    )
    assert response is not None


async def test_instructor_blocked_for_out_of_scope_student(pool, redis_client):
    """BLOCKED: an instructor cannot read a student in another department."""
    from app.tools.resources.departments.create import create_department

    tag = unique_tag()
    async with pool.acquire() as conn:
        dept_a = await create_department(
            conn, name=f"authz-rpt-a-{tag}", description="authz", redis=redis_client
        )
        dept_b = await create_department(
            conn, name=f"authz-rpt-b-{tag}", description="authz", redis=redis_client
        )

    instructor_artifact_id, _ = await _make_actor(
        pool, redis_client, role_level=2, department_ids=[dept_a.id]
    )
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=5, department_ids=[dept_b.id]
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    with pytest.raises(HTTPException) as exc:
        await _reports_for(
            pool,
            actor_artifact_id=instructor_artifact_id,
            target_profile_id=victim_resource_id,
        )
    assert exc.value.status_code == 403


async def test_superadmin_allowed_for_any_target(pool, redis_client):
    """ALLOWED: a role_level-0 superadmin may read any profile's report."""
    superadmin_artifact_id, _ = await _make_actor(pool, redis_client, role_level=0)
    _victim_artifact_id, victim_resource_id = await _make_actor(
        pool, redis_client, role_level=99
    )
    await _seed_attempt_chat_for(pool, redis_client, victim_resource_id)

    response = await _reports_for(
        pool,
        actor_artifact_id=superadmin_artifact_id,
        target_profile_id=victim_resource_id,
    )
    assert response is not None
