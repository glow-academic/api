"""Keycloak sync data resolvers — compose canonical black boxes.

Replaces load_sql + _detect_function_in_sql calls in keycloak_sync.py.
Each resolver returns plain dicts matching the original SQL return shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.artifacts.department.search import search_departments
from app.tools.artifacts.profile.get import get_profiles as get_profile_artifacts
from app.tools.artifacts.profile.search import search_profiles
from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.artifacts.setting.search import search_settings
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_values.get import get_auth_item_values
from app.tools.resources.auths.get import get_auths as get_auth_resources
from app.tools.resources.departments.get import (
    get_departments as get_department_resources,
)
from app.tools.resources.items.get import get_items
from app.tools.resources.keys.get import get_keys
from app.tools.resources.logins.get import get_logins
from app.tools.resources.profiles.get import get_profiles
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


# ── Resolver 1: Departments for org sync ───────────────────────────────
# Replaces: get_departments_for_org_sync_complete.sql


@dataclass
class DepartmentForSync:
    department_id: UUID
    department_name: str | None


async def resolve_departments_for_sync(
    conn: asyncpg.Connection,
    redis: Redis,
) -> list[DepartmentForSync]:
    """Active departments for Keycloak org sync.

    Composes: search_departments → get_departments (resource).
    """
    dept_artifact_ids, _ = await search_departments(conn, active_only=True, limit_count=100000)
    if not dept_artifact_ids:
        return []

    dept_arts = await get_department_artifacts(conn, dept_artifact_ids, departments=True)
    resource_ids = [a.department_ids[0] for a in dept_arts if a.department_ids]
    if not resource_ids:
        return []

    depts = await get_department_resources(conn, resource_ids, redis)
    # Map resource → artifact for stable department_id in results
    resource_to_artifact = {
        a.department_ids[0]: a.id for a in dept_arts if a.department_ids
    }
    return [
        DepartmentForSync(
            department_id=resource_to_artifact.get(d.id, d.id),
            department_name=d.name,
        )
        for d in depts
    ]


# ── Resolver 2: Auths for a department (org-scoped IdPs) ──────────────
# Replaces: get_auths_for_org_complete.sql


@dataclass
class AuthForSync:
    id: UUID
    slug: str | None
    provider_id: str | None
    name: str | None


async def resolve_auths_for_department(
    conn: asyncpg.Connection,
    redis: Redis,
    department_id: UUID,
) -> list[AuthForSync]:
    """Auths linked to a department via setting artifacts.

    Chain: department_artifact → resource ID → find settings with that dept
           → setting_logins_junction → logins_resource.auth_id → auth resources.
    """
    # Step 1: Get department's resource ID from self-link junction
    dept_arts = await get_department_artifacts(conn, [department_id], departments=True)
    if not dept_arts or not dept_arts[0].department_ids:
        return []
    dept_resource_id = dept_arts[0].department_ids[0]

    # Step 2: Get ALL setting artifacts with departments + logins junctions
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, departments=True, logins=True
    )

    # Step 3: Filter to settings linked to this department's resource ID
    logins_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if dept_resource_id in (sa.department_ids or []):
            if sa.logins_ids:
                logins_ids.update(sa.logins_ids)

    if not logins_ids:
        return []

    # Step 4: Resolve logins → collect auth_ids (login_type = 'auth')
    login_resources = await get_logins(conn, list(logins_ids), redis)
    auth_ids: set[UUID] = {
        lg.auth_id for lg in login_resources if lg.auth_id and lg.login_type == "auth"
    }
    if not auth_ids:
        return []

    # Step 5: Auth resources for slug/name
    auths = await get_auth_resources(conn, list(auth_ids), redis)
    return [
        AuthForSync(id=a.id, slug=a.slug, provider_id=a.protocol, name=a.name)
        for a in auths
        if a.active
    ]


# ── Resolver 3: Auths for realm level (default settings, no dept) ─────
# Replaces: get_auths_for_realm_level_complete.sql


async def resolve_auths_for_realm(
    conn: asyncpg.Connection,
    redis: Redis,
) -> list[AuthForSync]:
    """Auths from default settings (not linked to any department).

    Finds settings with empty department_ids (realm-level/platform defaults),
    then resolves their logins via setting_logins_junction and extracts auth IDs.
    """
    # Step 1: Get ALL active setting artifacts with departments + logins
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, departments=True, logins=True
    )

    # Step 2: Filter to realm-level (no department_ids)
    logins_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if not sa.department_ids:  # No departments = realm-level
            if sa.logins_ids:
                logins_ids.update(sa.logins_ids)

    if not logins_ids:
        return []

    # Step 3: Resolve logins → collect auth_ids (login_type = 'auth')
    login_resources = await get_logins(conn, list(logins_ids), redis)
    auth_ids: set[UUID] = {
        lg.auth_id for lg in login_resources if lg.auth_id and lg.login_type == "auth"
    }
    if not auth_ids:
        return []

    # Step 4: Get auth resources for slug/name
    auths = await get_auth_resources(conn, list(auth_ids), redis)
    return [
        AuthForSync(id=a.id, slug=a.slug, provider_id=a.protocol, name=a.name)
        for a in auths
        if a.active
    ]


# ── Resolver 4: Setting profiles for IdP sync ─────────────────────────
# Replaces: get_setting_profiles_for_idp_complete.sql


@dataclass
class SettingProfileForIdp:
    profile_id: UUID
    profile_name: str | None
    role: str | None
    setting_id: UUID
    department_id: UUID | None


async def resolve_setting_profiles_for_idp(
    conn: asyncpg.Connection,
    redis: Redis,
) -> list[SettingProfileForIdp]:
    """Profiles linked to active settings, with department scope.

    Composes: search_departments → get_departments (resource) → get_settings (artifact, profiles=True)
    → get_profiles (resource).
    """
    # Step 1: Build dept→setting_ids map and collect all setting resource IDs
    # Read through artifact junctions to get current resource IDs
    dept_artifact_ids, _ = await search_departments(conn, active_only=True, limit_count=100000)

    dept_setting_map: dict[UUID, list[UUID]] = {}  # setting_resource_id → dept_artifact_ids
    dept_setting_ids: set[UUID] = set()

    if dept_artifact_ids:
        dept_arts = await get_department_artifacts(conn, dept_artifact_ids, departments=True)
        resource_ids = [a.department_ids[0] for a in dept_arts if a.department_ids]
        depts = await get_department_resources(conn, resource_ids, redis) if resource_ids else []
        # Map resource_id → artifact_id for downstream lookups
        resource_to_artifact = {
            a.department_ids[0]: a.id for a in dept_arts if a.department_ids
        }
        for d in depts:
            if d.setting_ids:
                artifact_id = resource_to_artifact.get(d.id, d.id)
                for sid in d.setting_ids:
                    dept_setting_ids.add(sid)
                    dept_setting_map.setdefault(sid, []).append(artifact_id)

    # Step 2: Get ALL active setting artifacts with logins + settings junctions
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, logins=True, settings=True
    )

    # Step 3: Resolve logins → extract profile_resource_ids per setting
    # (login_type = 'profile' → login.profile_id is the profile resource ID)
    all_logins_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if sa.logins_ids:
            all_logins_ids.update(sa.logins_ids)

    login_map: dict[UUID, UUID] = {}  # logins_id → profile_resource_id
    if all_logins_ids:
        login_resources = await get_logins(conn, list(all_logins_ids), redis)
        login_map = {
            lg.id: lg.profile_id
            for lg in login_resources
            if lg.profile_id and lg.login_type == "profile"
        }

    # Build setting_artifact → (profile_resource_ids, settings_resource_ids)
    all_profile_resource_ids: set[UUID] = set()
    # (profile_resource_id, setting_artifact_id, settings_resource_id)
    profile_setting_links: list[tuple[UUID, UUID, UUID | None]] = []

    for sa in setting_artifacts:
        profile_resource_ids: list[UUID] = []
        for lid in sa.logins_ids or []:
            prid = login_map.get(lid)
            if prid and prid not in profile_resource_ids:
                profile_resource_ids.append(prid)
        settings_resource_ids = sa.setting_ids or []

        for prid in profile_resource_ids:
            all_profile_resource_ids.add(prid)
            if settings_resource_ids:
                for sr_id in settings_resource_ids:
                    profile_setting_links.append((prid, sa.id, sr_id))
            else:
                profile_setting_links.append((prid, sa.id, None))

    if not all_profile_resource_ids:
        return []

    # Step 4: Resolve profile resource IDs → artifact IDs
    # Search all profile artifacts with self-link to build resource→artifact map
    profile_artifact_ids, _ = await search_profiles(conn, active_only=True, limit_count=100000)
    profile_arts = await get_profile_artifacts(
        conn, profile_artifact_ids, profiles=True
    ) if profile_artifact_ids else []
    profile_resource_to_artifact: dict[UUID, UUID] = {
        a.profile_ids[0]: a.id for a in profile_arts if a.profile_ids
    }

    # Get profile resource details for name/role
    profiles = await get_profiles(conn, list(all_profile_resource_ids), redis)
    profile_map = {p.id: p for p in profiles}

    # Step 5: Build results with department scope (using artifact IDs)
    results: list[SettingProfileForIdp] = []
    seen: set[tuple[UUID, UUID | None]] = set()  # (profile_artifact_id, department_id)

    for prid, setting_artifact_id, sr_id in profile_setting_links:
        profile = profile_map.get(prid)
        if not profile or not profile.active:
            continue

        # Resolve profile resource ID → artifact ID
        profile_artifact_id = profile_resource_to_artifact.get(prid)
        if not profile_artifact_id:
            continue

        if sr_id and sr_id in dept_setting_ids:
            # Department-scoped
            for dept_id in dept_setting_map.get(sr_id, []):
                key = (profile_artifact_id, dept_id)
                if key not in seen:
                    seen.add(key)
                    results.append(
                        SettingProfileForIdp(
                            profile_id=profile_artifact_id,
                            profile_name=profile.name,
                            role=None,  # role column dropped from profiles_resource
                            setting_id=setting_artifact_id,
                            department_id=dept_id,
                        )
                    )
        else:
            # Default (non-department)
            key = (profile_artifact_id, None)
            if key not in seen:
                seen.add(key)
                results.append(
                    SettingProfileForIdp(
                        profile_id=profile_artifact_id,
                        profile_name=profile.name,
                        role=None,  # role column dropped from profiles_resource
                        setting_id=setting_artifact_id,
                        department_id=None,
                    )
                )

    return results


# ── Resolver 4b: Logins for a department (logins_resource via settings) ──


@dataclass
class LoginForSync:
    id: UUID
    profile_id: UUID | None
    auth_id: UUID | None
    icon_id: UUID | None
    display_name: str
    login_type: str


async def resolve_logins_for_department(
    conn: asyncpg.Connection,
    redis: Redis,
    department_id: UUID,
) -> list[LoginForSync]:
    """Logins linked to a department via setting artifacts.

    Chain: department_artifact -> resource ID -> find settings with that dept
           -> setting_logins_junction -> logins_resource.
    """
    # Step 1: Get department's resource ID from self-link junction
    dept_arts = await get_department_artifacts(conn, [department_id], departments=True)
    if not dept_arts or not dept_arts[0].department_ids:
        return []
    dept_resource_id = dept_arts[0].department_ids[0]

    # Step 2: Get ALL setting artifacts with departments + logins junctions
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, departments=True, logins=True
    )

    # Step 3: Filter to settings linked to this department's resource ID
    logins_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if dept_resource_id in (sa.department_ids or []):
            if sa.logins_ids:
                logins_ids.update(sa.logins_ids)

    if not logins_ids:
        return []

    # Step 4: Fetch logins_resource entries
    login_resources = await get_logins(conn, list(logins_ids), redis)
    return [
        LoginForSync(
            id=lr.id,
            profile_id=lr.profile_id,
            auth_id=lr.auth_id,
            icon_id=lr.icon_id,
            display_name=lr.display_name,
            login_type=lr.login_type,
        )
        for lr in login_resources
        if lr.active
    ]


# ── Resolver 4c: Logins for realm level (default settings, no dept) ──


async def resolve_logins_for_realm(
    conn: asyncpg.Connection,
    redis: Redis,
) -> list[LoginForSync]:
    """Logins from default settings (not linked to any department).

    Finds settings with empty department_ids (realm-level/platform defaults),
    then resolves their logins via setting_logins_junction.
    """
    # Step 1: Get ALL active setting artifacts with departments + logins
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, departments=True, logins=True
    )

    # Step 2: Filter to realm-level (no department_ids)
    logins_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if not sa.department_ids:  # No departments = realm-level
            if sa.logins_ids:
                logins_ids.update(sa.logins_ids)

    if not logins_ids:
        return []

    # Step 3: Fetch logins_resource entries
    login_resources = await get_logins(conn, list(logins_ids), redis)
    return [
        LoginForSync(
            id=lr.id,
            profile_id=lr.profile_id,
            auth_id=lr.auth_id,
            icon_id=lr.icon_id,
            display_name=lr.display_name,
            login_type=lr.login_type,
        )
        for lr in login_resources
        if lr.active
    ]


# ── Resolver 5: Auth items (config) with dept→default fallback ────────
# Replaces: get_auth_items_complete.sql


@dataclass
class AuthItem:
    name: str
    value: str
    encrypted: bool


async def resolve_auth_items(
    conn: asyncpg.Connection,
    redis: Redis,
    auth_id: UUID,
    department_id: UUID | None = None,
) -> list[AuthItem]:
    """Auth config items (name, value, encrypted) with dept-first, default fallback.

    Composes: get_auths (artifact) → get_items → get_departments (resource) →
    get_settings (artifact+resource) → get_auth_item_keys + get_keys (encrypted)
    or get_auth_item_values (non-encrypted).
    """
    # Step 1: Get auth artifact → item_ids
    auth_artifacts = await get_auth_artifacts(conn, [auth_id], items=True)
    if not auth_artifacts:
        return []

    item_ids = auth_artifacts[0].item_ids or []
    if not item_ids:
        return []

    # Step 2: Get items (name, encrypted flag)
    items = await get_items(conn, item_ids, redis)
    if not items:
        return []

    item_map = {i.id: i for i in items}

    # Step 3: Get department's resource ID for matching
    dept_resource_id: UUID | None = None
    if department_id:
        dept_arts = await get_department_artifacts(conn, [department_id], departments=True)
        if dept_arts and dept_arts[0].department_ids:
            dept_resource_id = dept_arts[0].department_ids[0]

    # Step 4: Get ALL active setting artifacts with departments + auth items
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn,
        setting_artifact_ids,
        departments=True,
        auth_item_keys=True,
        auth_item_values=True,
    )

    # Categorize setting artifacts into dept vs default using department_ids
    dept_auth_item_key_ids: list[UUID] = []
    dept_auth_item_value_ids: list[UUID] = []
    default_auth_item_key_ids: list[UUID] = []
    default_auth_item_value_ids: list[UUID] = []

    for sa in setting_artifacts:
        has_departments = bool(sa.department_ids)
        is_dept = dept_resource_id and dept_resource_id in (sa.department_ids or [])
        is_default = not has_departments

        if is_dept:
            if sa.auth_item_keys_ids:
                dept_auth_item_key_ids.extend(sa.auth_item_keys_ids)
            if sa.auth_item_value_ids:
                dept_auth_item_value_ids.extend(sa.auth_item_value_ids)
        if is_default:
            if sa.auth_item_keys_ids:
                default_auth_item_key_ids.extend(sa.auth_item_keys_ids)
            if sa.auth_item_value_ids:
                default_auth_item_value_ids.extend(sa.auth_item_value_ids)

    # Step 5: Fetch auth_item_keys + keys, auth_item_values sequentially
    # (cannot use asyncio.gather with a single asyncpg connection)
    all_key_ids = list(set(dept_auth_item_key_ids + default_auth_item_key_ids))
    all_value_ids = list(set(dept_auth_item_value_ids + default_auth_item_value_ids))

    auth_item_keys_list = (
        await get_auth_item_keys(conn, all_key_ids, redis) if all_key_ids else []
    )
    auth_item_values_list = (
        await get_auth_item_values(conn, all_value_ids, redis) if all_value_ids else []
    )

    # Step 6: Get actual key values for encrypted items
    key_resource_ids = list({aik.key_id for aik in auth_item_keys_list if aik.active})
    keys = await get_keys(conn, key_resource_ids, redis) if key_resource_ids else []
    key_value_map = {k.id: k.key for k in keys}

    # Step 7: Build results with dept-first, default-fallback
    dept_key_id_set = set(dept_auth_item_key_ids)
    default_key_id_set = set(default_auth_item_key_ids)
    dept_value_id_set = set(dept_auth_item_value_ids)
    default_value_id_set = set(default_auth_item_value_ids)

    # Encrypted items: auth_item_keys → keys
    encrypted_results: dict[str, AuthItem] = {}
    # Process dept-scoped first (higher priority)
    for aik in sorted(auth_item_keys_list, key=lambda x: x.created_at, reverse=True):
        if not aik.active or aik.auth_id != auth_id:
            continue
        item = item_map.get(aik.item_id)
        if not item or not item.encrypted:
            continue
        key_val = key_value_map.get(aik.key_id)
        if not key_val:
            continue

        is_dept = aik.id in dept_key_id_set
        is_default = aik.id in default_key_id_set

        if is_dept and item.name not in encrypted_results:
            encrypted_results[item.name] = AuthItem(
                name=item.name, value=key_val, encrypted=True
            )
        elif is_default and item.name not in encrypted_results:
            encrypted_results[item.name] = AuthItem(
                name=item.name, value=key_val, encrypted=True
            )

    # Non-encrypted items: auth_item_values
    non_encrypted_results: dict[str, AuthItem] = {}
    for aiv in sorted(auth_item_values_list, key=lambda x: x.created_at, reverse=True):
        if not aiv.active or aiv.auth_id != auth_id:
            continue
        item = item_map.get(aiv.item_id)
        if not item or item.encrypted:
            continue

        is_dept = aiv.id in dept_value_id_set
        is_default = aiv.id in default_value_id_set

        if is_dept and item.name not in non_encrypted_results:
            non_encrypted_results[item.name] = AuthItem(
                name=item.name, value=aiv.value, encrypted=False
            )
        elif is_default and item.name not in non_encrypted_results:
            non_encrypted_results[item.name] = AuthItem(
                name=item.name, value=aiv.value, encrypted=False
            )

    # Merge: encrypted takes priority over non-encrypted for same name
    combined: dict[str, AuthItem] = {}
    combined.update(non_encrypted_results)
    combined.update(encrypted_results)

    return list(combined.values())
