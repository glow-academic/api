"""Authorization tests for resolve_session_context (IDOR fix, issue #144).

A session detail read must be gated by the dashboard visibility policy:
the session's owner must be in the actor's visible-profile set. This proves
both directions:

  - Blocked: a member/instructor whose visible set excludes the owner gets a
    denied (empty) context — no victim timeline. FAILS pre-fix, PASSES post-fix.
  - Allowed (self): owner reading their own session gets full detail.
  - Allowed (visible): an instructor reading a same-department student's session.
  - Allowed (superadmin): role_level 0 reads any session (admin tooling preserved).

Black-box: profiles/roles/departments/sessions are built via the resource/entry
create tools; visibility comes from the real resolve_visible_profile_ids. No raw
SQL in the assertions, deps passed as params.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.session.context import resolve_session_context
from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions
from app.tools.resources.departments.create import create_department
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.roles.create import create_role
from tests.helpers import unique_tag

pytestmark = pytest.mark.asyncio


def _actor_context(
    *,
    profiles_id: UUID,
    role_name: str,
    role_level: int,
    department_ids: list[UUID],
) -> ProfileIdentityContext:
    """Build a minimal ProfileIdentityContext for an actor (deps-as-params)."""
    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="actor",
        role=role_name,
        role_name=role_name,
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=department_ids[0] if department_ids else None,
        department_ids=department_ids,
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
    )


async def _seed_victim_session(pool, redis_client, *, department_id: UUID, role_id: UUID):
    """Create a victim profile + an active session it owns. Returns (profile, session_id)."""
    tag = unique_tag()
    async with pool.acquire() as conn:
        victim = await create_profile(
            conn,
            redis_client,
            name=f"victim-{tag}",
            department_ids=[department_id],
            role_id=role_id,
        )
        session = await create_session(conn, redis_client, profile_id=victim.id)
        await refresh_sessions(conn)
    return victim, session.id


async def test_blocked_cross_profile_read_outside_visible_set(pool, redis_client):
    """A member whose visible set excludes the owner is denied (no timeline)."""
    tag = unique_tag()
    async with pool.acquire() as conn:
        victim_dept = await create_department(
            conn, name=f"authz-victim-dept-{tag}", description="", redis=redis_client
        )
        attacker_dept = await create_department(
            conn, name=f"authz-attacker-dept-{tag}", description="", redis=redis_client
        )
        member_role = await create_role(
            conn, redis_client, name=f"AuthZ Member {tag}", description="", level=5
        )
        attacker = await create_profile(
            conn,
            redis_client,
            name=f"attacker-{tag}",
            department_ids=[attacker_dept.id],
            role_id=member_role.id,
        )

    victim, session_id = await _seed_victim_session(
        pool, redis_client, department_id=victim_dept.id, role_id=member_role.id
    )

    actor = _actor_context(
        profiles_id=attacker.id,
        role_name=member_role.name,
        role_level=5,
        department_ids=[attacker_dept.id],
    )

    ctx = await resolve_session_context(
        pool,
        redis_client,
        session_id=session_id,
        profile_id=attacker.id,
        actor_profile=actor,
        bypass_cache=True,
    )

    # Denied: empty/denied context — no session, no victim timeline.
    assert ctx.entries["session"] is None
    assert ctx.entries["groups"] == []
    assert ctx.entries["logins"] == []
    assert ctx.entries["problems"] == []
    assert ctx.entries["chats"] == []


async def test_blocked_demonstrates_idor_without_gate(pool, redis_client):
    """Without the actor gate (actor_profile=None) the unscoped read still works.

    This pins the pre-fix behavior: the data layer resolves any session by id.
    The gate (actor_profile) is what closes it — see the blocked test above.
    """
    tag = unique_tag()
    async with pool.acquire() as conn:
        victim_dept = await create_department(
            conn, name=f"authz-idor-dept-{tag}", description="", redis=redis_client
        )
        member_role = await create_role(
            conn, redis_client, name=f"AuthZ IDOR Member {tag}", description="", level=5
        )
        attacker = await create_profile(
            conn,
            redis_client,
            name=f"idor-attacker-{tag}",
            department_ids=[victim_dept.id],
            role_id=member_role.id,
        )

    victim, session_id = await _seed_victim_session(
        pool, redis_client, department_id=victim_dept.id, role_id=member_role.id
    )

    # No actor_profile → no gate → unscoped read resolves the victim session.
    ctx = await resolve_session_context(
        pool,
        redis_client,
        session_id=session_id,
        profile_id=attacker.id,
        actor_profile=None,
        bypass_cache=True,
    )

    assert ctx.entries["session"] is not None
    assert ctx.entries["session"].profile_id == victim.id


async def test_allowed_self_read(pool, redis_client):
    """Owner reading their own session gets full detail."""
    tag = unique_tag()
    async with pool.acquire() as conn:
        dept = await create_department(
            conn, name=f"authz-self-dept-{tag}", description="", redis=redis_client
        )
        member_role = await create_role(
            conn, redis_client, name=f"AuthZ Self Member {tag}", description="", level=5
        )

    victim, session_id = await _seed_victim_session(
        pool, redis_client, department_id=dept.id, role_id=member_role.id
    )

    actor = _actor_context(
        profiles_id=victim.id,
        role_name=member_role.name,
        role_level=5,
        department_ids=[dept.id],
    )

    ctx = await resolve_session_context(
        pool,
        redis_client,
        session_id=session_id,
        profile_id=victim.id,
        actor_profile=actor,
        bypass_cache=True,
    )

    assert ctx.entries["session"] is not None
    assert ctx.entries["session"].profile_id == victim.id


async def test_allowed_instructor_reads_student_in_visible_set(pool, redis_client):
    """Instructor (lower level) reading a same-department student's session works."""
    tag = unique_tag()
    async with pool.acquire() as conn:
        dept = await create_department(
            conn, name=f"authz-cohort-dept-{tag}", description="", redis=redis_client
        )
        instructor_role = await create_role(
            conn, redis_client, name=f"AuthZ Instructor {tag}", description="", level=1
        )
        student_role = await create_role(
            conn, redis_client, name=f"AuthZ Student {tag}", description="", level=5
        )
        instructor = await create_profile(
            conn,
            redis_client,
            name=f"instructor-{tag}",
            department_ids=[dept.id],
            role_id=instructor_role.id,
        )

    student, session_id = await _seed_victim_session(
        pool, redis_client, department_id=dept.id, role_id=student_role.id
    )

    actor = _actor_context(
        profiles_id=instructor.id,
        role_name=instructor_role.name,
        role_level=1,
        department_ids=[dept.id],
    )

    ctx = await resolve_session_context(
        pool,
        redis_client,
        session_id=session_id,
        profile_id=instructor.id,
        actor_profile=actor,
        bypass_cache=True,
    )

    assert ctx.entries["session"] is not None
    assert ctx.entries["session"].profile_id == student.id


async def test_allowed_superadmin_reads_any_session(pool, redis_client):
    """role_level 0 reads any session — admin tooling preserved."""
    tag = unique_tag()
    async with pool.acquire() as conn:
        victim_dept = await create_department(
            conn, name=f"authz-admin-dept-{tag}", description="", redis=redis_client
        )
        admin_dept = await create_department(
            conn, name=f"authz-admin-actor-dept-{tag}", description="", redis=redis_client
        )
        member_role = await create_role(
            conn, redis_client, name=f"AuthZ Admin Victim Role {tag}", description="", level=5
        )
        super_role = await create_role(
            conn, redis_client, name=f"AuthZ Super {tag}", description="", level=0
        )
        superadmin = await create_profile(
            conn,
            redis_client,
            name=f"superadmin-{tag}",
            department_ids=[admin_dept.id],
            role_id=super_role.id,
        )

    victim, session_id = await _seed_victim_session(
        pool, redis_client, department_id=victim_dept.id, role_id=member_role.id
    )

    actor = _actor_context(
        profiles_id=superadmin.id,
        role_name=super_role.name,
        role_level=0,
        department_ids=[admin_dept.id],
    )

    ctx = await resolve_session_context(
        pool,
        redis_client,
        session_id=session_id,
        profile_id=superadmin.id,
        actor_profile=actor,
        bypass_cache=True,
    )

    assert ctx.entries["session"] is not None
    assert ctx.entries["session"].profile_id == victim.id
