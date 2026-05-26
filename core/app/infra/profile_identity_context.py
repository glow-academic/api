"""Resolve profile identity context from a profile artifact ID.

Given a profile_id (artifact), fetches the profile artifact's junctions,
hydrates resources in parallel, and returns a clean ProfileIdentityContext with
identity, role metadata, emails, departments, and settings.

Used by common_context to resolve the logged-in user's identity.
Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.primary_departments.get import (
    get_primary_departments,
)
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.request_limits.get import get_request_limits
from app.tools.resources.roles.get import get_roles

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileIdentityContext:
    """Hydrated profile context for use by downstream infra layers."""

    profiles_id: UUID  # resource ID (from profile_profiles_junction)
    name: str
    role: str  # role name (e.g., "Super Administrator") — used for identity
    role_name: str  # display name from roles_resource (same as role)
    role_description: str
    role_artifacts: list[str]  # artifact types this role can access (derived from permissions)
    primary_email: str | None
    emails: list[str]  # all emails
    primary_department_id: UUID | None
    department_ids: list[UUID]  # all department IDs
    # ``settings_resource.id`` (the resource id), NOT ``setting_artifact.id``.
    # Comes from ``primary_dept.setting_ids[0]`` which is itself a resource id.
    # Consumers needing the artifact id (e.g. theme path) translate internally
    # via ``setting_settings_junction``.
    settings_id: UUID | None
    request_limit: int | None  # rate limit from role's request_limit_ids
    request_limit_interval: str | None  # interval (e.g. "1 day") from request_limits_resource
    is_active: bool
    # Fields with defaults must come after fields without defaults
    role_level: int = 99  # hierarchy level (0 = highest privilege)
    session_id: UUID | None = None
    role_permissions: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# resolve_profile_identity_context
# ---------------------------------------------------------------------------


async def resolve_profile_identity_context(
    pool: asyncpg.Pool,
    profile_id: UUID,
    redis: Redis,
    bypass_cache: bool = False,
    # Server-resolved session (from require_auth middleware)
    session_id: UUID | None = None,
) -> ProfileIdentityContext | None:
    """Resolve a profile artifact ID into a hydrated ProfileIdentityContext.

    Pure identity: profile, role, departments, session. No group resolution.
    Callers that need a group_id must resolve it themselves via either
    ``app.infra.identity.group.resolve_group`` (attempt/test context) or
    ``app.infra.group.resolve.resolve_group_impl`` (fresh per-artifact group).

    Steps:
      1. get_profile_artifacts — fetches junction IDs
      2. asyncio.gather — hydrates all resources in parallel
      3. Pure Python assembly
    """
    # Step 1: fetch profile artifact with all needed junctions
    async with pool.acquire() as conn:
        artifacts = await get_profile_artifacts(
            conn,
            [profile_id],
            active=None,
            names=True,
            roles=True,
            departments=True,
            emails=True,
            profiles=True,
            flags=True,
            primary_departments=True,
        )

    if not artifacts:
        return None

    artifact = artifacts[0]

    # Extract junction IDs
    name_ids = artifact.name_ids or []
    role_ids = artifact.role_ids or []
    department_ids = artifact.department_ids or []
    email_ids = artifact.email_ids or []
    profile_ids = artifact.profile_ids or []
    primary_department_resource_ids = artifact.primary_department_ids or []

    if not profile_ids:
        return None

    profiles_id = profile_ids[0]

    # Step 2: hydrate all resources in parallel

    # The 5 primitives now take Pool instead of Connection — cache check
    # happens before any server conn is acquired. On a cache hit (the 96%
    # case) zero pgbouncer conns are pinned, removing the 5x fan-out
    # pressure that previously saturated the pool under page-load bursts.
    async def _get_names() -> list:
        if not name_ids:
            return []
        return await get_names(pool, name_ids, redis, bypass_cache)

    async def _get_roles() -> list:
        if not role_ids:
            return []
        return await get_roles(pool, role_ids, redis, bypass_cache)

    async def _get_departments() -> list:
        if not department_ids:
            return []
        return await get_departments(pool, department_ids, redis, bypass_cache)

    async def _get_emails() -> list:
        if not email_ids:
            return []
        return await get_emails(pool, email_ids, redis, bypass_cache)

    async def _get_profiles() -> list:
        return await get_profiles(pool, profile_ids, redis, bypass_cache)

    async def _get_primary_departments() -> list:
        if not primary_department_resource_ids:
            return []
        return await get_primary_departments(pool, primary_department_resource_ids, redis, bypass_cache
        )

    (
        names_res,
        roles_res,
        depts_res,
        emails_res,
        profiles_res,
        primary_depts_res,
    ) = await asyncio.gather(
        _get_names(),
        _get_roles(),
        _get_departments(),
        _get_emails(),
        _get_profiles(),
        _get_primary_departments(),
    )

    # Step 3: extract values
    name = names_res[0].name if names_res else ""

    role = ""
    role_level = 99
    role_name = ""
    role_description = ""
    role_artifacts: list[str] = []
    role_permissions: list[tuple[str, str]] = []
    if roles_res:
        r = roles_res[0]
        role = r.name
        role_level = r.level
        role_name = r.name
        role_description = r.description

        # Resolve permissions from permission_ids to derive artifacts + operations
        perm_ids = r.permission_ids or []
        if perm_ids:
            perms = await get_permissions(pool, perm_ids, redis, bypass_cache)
            role_permissions = [(p.artifact, p.operation) for p in perms]
            # Derive unique artifact strings for sidebar visibility
            role_artifacts = list(dict.fromkeys(p.artifact for p in perms))

    # Rate limit from role's request_limit_ids
    request_limit: int | None = None
    request_limit_interval: str | None = None
    if roles_res:
        rl_ids = roles_res[0].request_limit_ids or []
        if rl_ids:
            rl_items = await get_request_limits(pool, rl_ids, redis, bypass_cache)
            if rl_items:
                request_limit = rl_items[0].limit
                request_limit_interval = rl_items[0].interval

    # Primary department: read from profile_primary_departments_junction →
    # primary_departments_resource → departments_resource. The dept's
    # ``setting_ids`` array stores the canonical setting *resource* id
    # (the denormalized snapshot pointer), and ``ProfileIdentityContext.
    # settings_id`` is documented to be that resource id — every direct
    # consumer here passes it to a ``settings_resource``-keyed getter
    # (``resolve_tool_graph`` → ``get_settings`` resource version,
    # ``mcp/resolve.py`` → same). The one consumer that needs the
    # artifact id (``resolve_settings_theme``, for the theme/colors
    # path) does the resource→artifact translation internally via the
    # ``setting_settings_junction`` black-box, so we don't need to do
    # it here.
    primary_department_id: UUID | None = None
    settings_id: UUID | None = None
    if primary_depts_res:
        primary_department_id = primary_depts_res[0].departments_id
        primary_dept = next(
            (d for d in depts_res if d.id == primary_department_id),
            None,
        )
        if primary_dept and primary_dept.setting_ids:
            settings_id = primary_dept.setting_ids[0]

    # Fallback: profile has no primary department (fresh deploys / guests /
    # never-assigned profiles) — resolve the platform-default setting (one
    # whose ``department_ids`` is empty). Mirrors the realm-level fallback
    # used by ``keycloak_resolvers.resolve_auths_for_realm``. Without this,
    # ``settings_id`` would stay ``None`` and theme resolution would return
    # nothing, silently rendering shadcn defaults instead of the seeded
    # LearnLoop palette.
    if settings_id is None:
        from app.infra.identity.settings import (
            resolve_platform_default_settings_resource_id,
        )
        settings_id = await resolve_platform_default_settings_resource_id(pool)

    # Primary email: find the one with is_primary=True on the resource
    primary_email: str | None = None
    for email in emails_res:
        if email.is_primary:
            primary_email = email.email
            break

    all_emails = [e.email for e in emails_res]
    all_department_ids = [d.id for d in depts_res]

    # is_active: check if profile has an active "profile_active" flag
    # The artifact's active field reflects this
    is_active = artifact.active

    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name=name,
        role=role,
        role_name=role_name,
        role_description=role_description,
        role_artifacts=role_artifacts,
        role_level=role_level,
        role_permissions=role_permissions,
        primary_email=primary_email,
        emails=all_emails,
        primary_department_id=primary_department_id,
        department_ids=all_department_ids,
        settings_id=settings_id,
        request_limit=request_limit,
        request_limit_interval=request_limit_interval,
        is_active=is_active,
        session_id=session_id,
    )
