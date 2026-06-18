"""Shared helpers for artifact route tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.groups.create import create_group
from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions
from tests.helpers import unique_tag


def selected_resource(section: list[dict] | dict | None) -> dict:
    """Return the selected item from a route-response resource section.

    The canonical artifact responses moved each resource section from the old
    ``{"resource": {...}, "resources": [...]}`` envelope to a flat list of
    items where the currently selected item carries ``selected: true``. This
    helper preserves the original test intent ("the selected resource") across
    that shape change: it accepts the new flat list and returns the selected
    item (falling back to the sole/first item when no flag is set), and stays
    backward-compatible with the legacy envelope by unwrapping ``resource``.
    """
    if section is None:
        raise AssertionError("Expected a resource section, got None")
    if isinstance(section, dict):
        # Legacy envelope shape: {"resource": {...}, "resources": [...]}.
        return section["resource"]
    if not section:
        raise AssertionError("Expected a non-empty resource section")
    for item in section:
        if item.get("selected"):
            return item
    return section[0]


def selected_resources(section: list[dict] | dict | None) -> list[dict]:
    """Return the currently selected items from a route-response section.

    Counterpart to :func:`selected_resource` for multi-select association
    sections (departments, profiles, scenarios, ...). These moved from the old
    ``{"current": [...], "resources": [...]}`` envelope to a flat list where
    each selected item carries ``selected: true``. This helper preserves the
    original ``section["current"]`` intent across that change and stays
    backward-compatible with the legacy envelope.
    """
    if section is None:
        raise AssertionError("Expected a resource section, got None")
    if isinstance(section, dict):
        # Legacy envelope shape: {"current": [...], "resources": [...]}.
        return section["current"] or []
    return [item for item in section if item.get("selected")]


@dataclass(frozen=True)
class RouteActor:
    """Minimal authenticated actor for route-level tests."""

    profile_id: UUID
    profiles_id: UUID
    session_id: UUID
    department_id: UUID
    role_id: UUID
    name: str


async def create_admin_route_actor(
    pool,
    redis_client,
    setting_graph_factory,
    *,
    tool_artifacts: list[str] | None = None,
    extra_permissions: list[tuple[str, str]] | None = None,
    group_name: str,
    role_name_prefix: str,
    role: str = "admin",
    canonical_role_name: str | None = None,
) -> RouteActor:
    """Create a route actor with a requested role, session, and group.

    ``extra_permissions`` grants additional ``(artifact, operation)`` pairs
    beyond the standard CRUD set — e.g. the ``("attempt", "start")``
    permission the attempt lifecycle endpoints gate on, which is not one
    of the default operations.

    ``canonical_role_name`` assigns an exact, un-suffixed role name (e.g.
    ``"Super Administrator"``) instead of the default unique-tagged name.
    Emulation gates key ``SIMULATABLE_ROLES`` on the literal role name, so
    callers exercising ``/emulate`` must pass a canonical simulatable key
    here; the default tagged names are intentionally outside that set.
    """
    from app.tools.artifacts.profile.update import update_profile
    from app.tools.resources.permissions.create import create_permission
    from app.tools.resources.roles.create import create_role

    graph = await setting_graph_factory(
        tool_artifacts=tool_artifacts or ["persona", "scenario"],
    )

    async with pool.acquire() as conn:
        permission_ids = []
        for artifact in tool_artifacts or ["persona", "scenario"]:
            for operation in (
                "create",
                "read",
                "search",
                "update",
                "delete",
                "duplicate",
                "draft",
                # ``export`` is now gated by run_artifact_operation_with_audit
                # (the export family was systemically ungated). Route-test
                # actors are admins who legitimately hold it, so grant it by
                # default — otherwise every */export route test would 403.
                "export",
            ):
                permission = await create_permission(
                    conn,
                    artifact,
                    operation,
                    redis_client,
                )
                permission_ids.append(permission.id)

        for artifact, operation in extra_permissions or []:
            permission = await create_permission(
                conn,
                artifact,
                operation,
                redis_client,
            )
            permission_ids.append(permission.id)

        admin_role = await create_role(
            conn,
            redis_client,
            name=canonical_role_name or f"{role_name_prefix} {unique_tag()}",
            description=f"{group_name} {role} role",
            level=0 if role == "superadmin" else 1,
            permission_ids=permission_ids,
        )
        await update_profile(
            conn,
            graph.profile_artifact_id,
            role_ids=[admin_role.id],
            redis=redis_client,
        )
        session = await create_session(conn, redis_client, profile_id=graph.profile_resource_id)
        await refresh_sessions(conn)
        await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")

    identity = await resolve_profile_identity_context(
        pool,
        graph.profile_artifact_id,
        redis_client,
        session_id=session.id,
    )
    if identity is None:
        raise AssertionError("Expected route test actor identity to exist")

    return RouteActor(
        profile_id=graph.profile_artifact_id,
        profiles_id=graph.profile_resource_id,
        session_id=session.id,
        department_id=graph.department_id,
        role_id=admin_role.id,
        name=identity.name,
    )
