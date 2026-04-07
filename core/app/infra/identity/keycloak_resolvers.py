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
    dept_ids, _ = await search_departments(conn, active_only=True, limit_count=100000)
    if not dept_ids:
        return []

    depts = await get_department_resources(conn, dept_ids, redis)
    return [
        DepartmentForSync(department_id=d.id, department_name=d.name) for d in depts
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
    """Auths linked to a department via artifact junctions.

    Chain: department_artifact → department_settings_junction → setting_artifact
           → setting_auths_junction → auth_artifact → auth_resource (slug/name).
    """
    # Step 1: Department artifact → setting artifact IDs (via junction)
    dept_artifacts = await get_department_artifacts(
        conn, [department_id], settings=True
    )
    if not dept_artifacts:
        return []

    setting_artifact_ids = dept_artifacts[0].settings_ids or []
    if not setting_artifact_ids:
        return []

    # Step 2: Setting artifacts → auth artifact IDs (via junction)
    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, auths=True
    )

    auth_ids: set[UUID] = set()
    for sa in setting_artifacts:
        if sa.auth_ids:
            auth_ids.update(sa.auth_ids)

    if not auth_ids:
        return []

    # Step 3: Auth resources for slug/name
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

    Uses artifact junctions to find settings NOT linked to any department,
    then resolves their auths via setting_auths_junction.
    """
    # Step 1: Collect ALL setting artifact IDs linked to departments (via junctions)
    dept_ids, _ = await search_departments(conn, active_only=True, limit_count=100000)
    dept_setting_ids: set[UUID] = set()
    if dept_ids:
        dept_artifacts = await get_department_artifacts(conn, dept_ids, settings=True)
        for da in dept_artifacts:
            if da.settings_ids:
                dept_setting_ids.update(da.settings_ids)

    # Step 2: Get ALL active setting artifact IDs
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    # Step 3: Filter to realm-level (not linked to any department)
    realm_setting_ids = [
        sid for sid in setting_artifact_ids if sid not in dept_setting_ids
    ]
    if not realm_setting_ids:
        return []

    # Step 4: Get auth artifact IDs via setting_auths_junction
    realm_settings = await get_setting_artifacts(conn, realm_setting_ids, auths=True)

    auth_ids: set[UUID] = set()
    for sa in realm_settings:
        if sa.auth_ids:
            auth_ids.update(sa.auth_ids)

    if not auth_ids:
        return []

    # Step 5: Get auth resources for slug/name
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
    dept_ids, _ = await search_departments(conn, active_only=True, limit_count=100000)

    dept_setting_map: dict[UUID, list[UUID]] = {}  # setting_resource_id → dept_ids
    dept_setting_ids: set[UUID] = set()

    if dept_ids:
        depts = await get_department_resources(conn, dept_ids, redis)
        for d in depts:
            if d.setting_ids:
                for sid in d.setting_ids:
                    dept_setting_ids.add(sid)
                    dept_setting_map.setdefault(sid, []).append(d.id)

    # Step 2: Get ALL active setting artifacts with profiles junction
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn, setting_artifact_ids, profiles=True, settings=True
    )

    # Step 3: Build setting_artifact → (profile_ids, settings_resource_ids)
    # and collect all profile IDs
    all_profile_ids: set[UUID] = set()
    # (profile_id, setting_artifact_id, settings_resource_id)
    profile_setting_links: list[tuple[UUID, UUID, UUID | None]] = []

    for sa in setting_artifacts:
        profile_ids = sa.profile_ids or []
        settings_resource_ids = sa.setting_ids or []

        for pid in profile_ids:
            all_profile_ids.add(pid)
            # Link profile to each settings_resource_id for dept lookup
            if settings_resource_ids:
                for sr_id in settings_resource_ids:
                    profile_setting_links.append((pid, sa.id, sr_id))
            else:
                profile_setting_links.append((pid, sa.id, None))

    if not all_profile_ids:
        return []

    # Step 4: Get profile details
    profiles = await get_profiles(conn, list(all_profile_ids), redis)
    profile_map = {p.id: p for p in profiles}

    # Step 5: Build results with department scope
    results: list[SettingProfileForIdp] = []
    seen: set[tuple[UUID, UUID | None]] = set()  # (profile_id, department_id)

    for pid, setting_artifact_id, sr_id in profile_setting_links:
        profile = profile_map.get(pid)
        if not profile or not profile.active:
            continue

        if sr_id and sr_id in dept_setting_ids:
            # Department-scoped
            for dept_id in dept_setting_map.get(sr_id, []):
                key = (pid, dept_id)
                if key not in seen:
                    seen.add(key)
                    results.append(
                        SettingProfileForIdp(
                            profile_id=pid,
                            profile_name=profile.name,
                            role=profile.role,
                            setting_id=setting_artifact_id,
                            department_id=dept_id,
                        )
                    )
        else:
            # Default (non-department)
            key = (pid, None)
            if key not in seen:
                seen.add(key)
                results.append(
                    SettingProfileForIdp(
                        profile_id=pid,
                        profile_name=profile.name,
                        role=profile.role,
                        setting_id=setting_artifact_id,
                        department_id=None,
                    )
                )

    return results


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

    # Step 3: Resolve department settings and default settings
    dept_setting_ids: set[UUID] = set()
    all_dept_setting_ids: set[UUID] = set()

    if department_id:
        depts = await get_department_resources(conn, [department_id], redis)
        if depts and depts[0].setting_ids:
            dept_setting_ids.update(depts[0].setting_ids)

    # Get all department setting_ids (to identify defaults as "not in any dept")
    dept_ids_all, _ = await search_departments(
        conn, active_only=True, limit_count=100000
    )
    if dept_ids_all:
        all_depts = await get_department_resources(conn, dept_ids_all, redis)
        for d in all_depts:
            if d.setting_ids:
                all_dept_setting_ids.update(d.setting_ids)

    # Step 4: Get ALL active setting artifacts with auth_item_keys + auth_item_values junctions
    setting_artifact_ids, _ = await search_settings(
        conn, active_only=True, limit_count=100000
    )
    if not setting_artifact_ids:
        return []

    setting_artifacts = await get_setting_artifacts(
        conn,
        setting_artifact_ids,
        auth_item_keys=True,
        auth_item_values=True,
        settings=True,
    )

    # Categorize setting artifacts into dept vs default
    dept_auth_item_key_ids: list[UUID] = []
    dept_auth_item_value_ids: list[UUID] = []
    default_auth_item_key_ids: list[UUID] = []
    default_auth_item_value_ids: list[UUID] = []

    for sa in setting_artifacts:
        settings_resource_ids = sa.setting_ids or []
        is_dept = any(sr_id in dept_setting_ids for sr_id in settings_resource_ids)
        is_default = any(
            sr_id not in all_dept_setting_ids for sr_id in settings_resource_ids
        )

        if is_dept:
            if sa.auth_item_keys_ids:
                dept_auth_item_key_ids.extend(sa.auth_item_keys_ids)
            if sa.auth_item_value_ids:
                dept_auth_item_value_ids.extend(sa.auth_item_value_ids)
        if is_default and not is_dept:
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
