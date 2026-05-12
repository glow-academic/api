"""Generate Keycloak theme provider mapping + theme tokens from database.

Two generated artifacts:
  - ``login/providers.ftl`` — department→IdP allow-list (existing).
  - ``login/theme-vars.ftl`` — per-department CSS-variable palettes
    (light + dark), driven by each department's setting via
    ``resolve_settings_theme`` + ``derive_theme_tokens``. Identical
    tokens to the post-login dashboard, so the login → app transition
    is visually continuous.

Both files are FreeMarker variable includes consumed by templates in
the same directory.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_redis_client
from app.infra.identity.keycloak_resolvers import (
    LoginForSync,
    resolve_auths_for_department,
    resolve_auths_for_realm,
    resolve_departments_for_sync,
    resolve_logins_for_department,
    resolve_logins_for_realm,
    resolve_setting_profiles_for_idp,
)
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.resources.auths.get import get_auths as get_auth_resources
from app.tools.resources.departments.get import (
    get_departments as get_department_resources,
)
from app.tools.resources.icons.get import get_icons
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def generate_keycloak_theme_providers(pool: Any) -> None:
    """Generate comprehensive provider mapping covering ALL department and IdP combinations.

    Enumerates:
    - ALL departments: Active departments with IDs and titles
    - ALL IdP aliases: realm-level slugs + department-scoped auth_{slug}_{auth_id}
    - Complete mapping: department_id -> [allowed IdP aliases]
    - Platform fallback: Realm-level IdPs for when no department is selected

    Args:
        pool: Database connection pool
    """
    departments_list: list[dict[str, str]] = []
    allowed_providers_by_dept: dict[str, list[str]] = {}
    platform_providers: list[str] = []
    all_idp_aliases: set[str] = set()
    default_idp_aliases: set[str] = set()
    profile_aliases_by_dept: dict[str, list[str]] = {}
    platform_profile_aliases: list[str] = []

    # Logins data (new path — built alongside auth/profile for transition)
    realm_logins: list[dict] = []
    logins_by_dept: dict[str, list[dict]] = {}

    redis = get_redis_client()

    async with pool.acquire() as conn:
        # Step 1: Get ALL realm-level IdP aliases (for platform fallback)
        realm_level_auths = await resolve_auths_for_realm(conn, redis)
        platform_providers = [a.slug or "" for a in realm_level_auths]
        all_idp_aliases.update(platform_providers)

        # Step 1b: Resolve realm-level logins (new logins_resource path)
        _all_login_objects: list[LoginForSync] = []
        try:
            _realm_logins = await resolve_logins_for_realm(conn, redis)
            _all_login_objects.extend(_realm_logins)
            realm_logins = [
                {
                    "id": str(lg.id),
                    "display_name": lg.display_name,
                    "login_type": lg.login_type,
                    "auth_id": str(lg.auth_id) if lg.auth_id else None,
                    "profile_id": str(lg.profile_id) if lg.profile_id else None,
                    "icon_id": str(lg.icon_id) if lg.icon_id else None,
                }
                for lg in _realm_logins
            ]
        except Exception as e:
            logger.warning(f"Failed to resolve realm logins (non-fatal): {e}")
            realm_logins = []

        # Step 2: Get all default-idp profile aliases (per settings)
        setting_profiles = await resolve_setting_profiles_for_idp(conn, redis)

        # First pass: collect department-scoped profile aliases
        dept_scoped_aliases: set[str] = set()
        for sp in setting_profiles:
            profile_id = str(sp.profile_id)
            alias = f"default-idp-profile-{profile_id}"

            default_idp_aliases.add(alias)
            all_idp_aliases.add(alias)

            if sp.department_id:
                dept_key = str(sp.department_id)
                dept_aliases_list = profile_aliases_by_dept.setdefault(dept_key, [])
                if alias not in dept_aliases_list:
                    dept_aliases_list.append(alias)
                dept_scoped_aliases.add(alias)

        # Second pass: platform-level only for profiles NOT already department-scoped
        for sp in setting_profiles:
            profile_id = str(sp.profile_id)
            alias = f"default-idp-profile-{profile_id}"
            if not sp.department_id and alias not in dept_scoped_aliases:
                if alias not in platform_profile_aliases:
                    platform_profile_aliases.append(alias)

        # Step 3: Get ALL departments with titles
        departments = await resolve_departments_for_sync(conn, redis)
        has_departments = len(departments) > 0

        # Step 4: For each department, get its allowed IdPs and profile-default IdPs
        for dept in departments:
            dept_id = str(dept.department_id)
            dept_name = dept.department_name or dept_id

            departments_list.append({"id": dept_id, "title": dept_name})

            # Get logins for this department (new path)
            try:
                dept_logins = await resolve_logins_for_department(
                    conn, redis, dept.department_id
                )
                _all_login_objects.extend(dept_logins)
                logins_by_dept[dept_id] = [
                    {
                        "id": str(lg.id),
                        "display_name": lg.display_name,
                        "login_type": lg.login_type,
                        "auth_id": str(lg.auth_id) if lg.auth_id else None,
                        "profile_id": str(lg.profile_id) if lg.profile_id else None,
                        "icon_id": str(lg.icon_id) if lg.icon_id else None,
                    }
                    for lg in dept_logins
                ]
            except Exception as e:
                logger.warning(f"Failed to resolve logins for dept {dept_id} (non-fatal): {e}")

            # Get auths for this department
            dept_auths = await resolve_auths_for_department(
                conn, redis, dept.department_id
            )

            dept_aliases: list[str] = []
            dept_aliases_set: set[str] = set()
            for a in dept_auths:
                alias = f"auth_{a.slug}_{a.id}"
                if alias not in dept_aliases_set:
                    dept_aliases.append(alias)
                    dept_aliases_set.add(alias)
            all_idp_aliases.update(dept_aliases)

            # Add default-idp profile aliases for this department
            for alias in profile_aliases_by_dept.get(dept_id, []):
                if alias not in dept_aliases_set:
                    dept_aliases.append(alias)
                    dept_aliases_set.add(alias)

            allowed_providers_by_dept[dept_id] = dept_aliases

        # Step 5: Add platform-level default-idp profile aliases ONLY if there are no departments
        if not has_departments:
            for alias in platform_profile_aliases:
                if alias not in platform_providers:
                    platform_providers.append(alias)

        # Step 6: Resolve icon SVGs and auth aliases for loginEntries
        login_entries = await _resolve_login_entries(
            conn, redis, _all_login_objects
        )

    # Step 4: Generate FreeMarker file with department-based mapping
    # Use UPLOAD_FOLDER constant for consistent routing (works in Docker and local dev)
    out_path = UPLOAD_FOLDER / "themes/glow/login/providers.ftl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("<#-- GENERATED FILE: do not edit manually -->")
    lines.append(f"<#-- Generated at: {datetime.now().isoformat()} -->")
    lines.append("<#--")
    lines.append("  Provider mapping: department_id -> allowed IdP aliases")
    lines.append("")
    lines.append("  Enumerated departments:")
    for dept in departments_list:
        lines.append(f"    - {dept['id']}: {dept['title']}")
    lines.append("")
    lines.append("  Enumerated IdP aliases:")
    for alias in sorted(all_idp_aliases):
        lines.append(f"    - {alias}")
    lines.append("")
    lines.append("  Default-IdP aliases:")
    for alias in sorted(default_idp_aliases):
        lines.append(f"    - {alias}")
    lines.append("-->")
    lines.append("")

    # Generate departments array
    lines.append("<#-- Departments to show in the picker -->")
    lines.append("<#assign departments = [")
    for i, dept in enumerate(departments_list):
        comma = "," if i < len(departments_list) - 1 else ""
        lines.append(f'  {{"id": "{dept["id"]}", "title": "{dept["title"]}"}}{comma}')
    lines.append("] />")
    lines.append("")

    # Generate department -> IdP mapping
    lines.append("<#-- Map department_id -> allowed IdP aliases -->")
    lines.append("<#assign allowedProvidersByDept = {")
    for i, (dept_id, aliases) in enumerate(sorted(allowed_providers_by_dept.items())):
        alias_list = ", ".join([f'"{a}"' for a in aliases])
        comma = "," if i < len(allowed_providers_by_dept) - 1 else ""
        lines.append(f'  "{dept_id}": [{alias_list}]{comma}')
    lines.append("} />")
    lines.append("")

    # Generate platform providers (only used when no departments exist)
    lines.append("<#-- Platform providers (only used when no departments exist) -->")
    platform_list = ", ".join([f'"{p}"' for p in platform_providers])
    lines.append(f"<#assign platformProviders = [{platform_list}] />")
    lines.append("")

    # Generate function
    # Strategy: If departments exist, always use department-specific providers (default to first if none selected)
    # If no departments exist, use platform providers
    lines.append("<#function getAllowedProvidersForDepartment deptId>")
    lines.append(
        "  <#-- If departments exist, always use department-specific providers -->"
    )
    lines.append("  <#if departments?size gt 0>")
    lines.append("    <#-- Default to first department if no department selected -->")
    lines.append('    <#assign effectiveDeptId = deptId!"" />')
    lines.append("    <#if !effectiveDeptId?has_content>")
    lines.append("      <#assign effectiveDeptId = departments[0].id />")
    lines.append("    </#if>")
    lines.append(
        "    <#if effectiveDeptId?has_content && allowedProvidersByDept[effectiveDeptId]??>"
    )
    lines.append(
        "      <#assign deptProviders = allowedProvidersByDept[effectiveDeptId] />"
    )
    lines.append("      <#if deptProviders?size gt 0>")
    lines.append("        <#return deptProviders>")
    lines.append("      </#if>")
    lines.append("    </#if>")
    lines.append(
        "    <#-- Fallback: return empty list if department has no providers -->"
    )
    lines.append("    <#return []>")
    lines.append("  <#else>")
    lines.append("    <#-- No departments exist: use platform providers -->")
    lines.append("    <#return platformProviders>")
    lines.append("  </#if>")
    lines.append("</#function>")

    # Logins entries with inline SVG icons (loginEntries variable)
    lines.append("")
    lines.append("<#-- ═══ Login Entries (logins_resource with inline SVG icons) ═══ -->")
    lines.append("<#assign loginEntries = [")
    for i, le in enumerate(login_entries):
        comma = "," if i < len(login_entries) - 1 else ""
        # Escape SVG for safe embedding in FreeMarker string literal
        escaped_svg = _escape_ftl_string(le.get("icon_svg", ""))
        lines.append(
            f'  {{"alias": "{le["alias"]}", '
            f'"display_name": "{_escape_ftl_string(le["display_name"])}", '
            f'"icon_svg": "{escaped_svg}", '
            f'"login_type": "{le["login_type"]}"}}{comma}'
        )
    lines.append("] />")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"✅ Generated theme provider mapping: {out_path.resolve()}")
    logger.info(f"   - {len(departments_list)} departments enumerated")
    logger.info(f"   - {len(all_idp_aliases)} IdP aliases enumerated")
    logger.info(f"   - {len(login_entries)} login entries with icons")
    logger.info(f"   - {len(logins_by_dept)} departments with logins data")


def _escape_ftl_string(s: str) -> str:
    """Escape a string for safe embedding in a FreeMarker string literal.

    Handles backslashes, double quotes, and newlines.
    """
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", "")
    )


# ────────────────────────────────────────────────────────────────────────────
# theme-vars.ftl generator
# ────────────────────────────────────────────────────────────────────────────


async def _resolve_dept_setting_resource_id(
    conn: Any,
    redis: Any,
    department_artifact_id: UUID,
) -> UUID | None:
    """Find the setting *resource* id for a department.

    The setting resource id is the canonical pointer stored on
    ``departments_resource.setting_ids[0]``. Downstream callers (like
    ``resolve_settings_theme``) handle the resource→artifact
    translation internally — we don't pre-translate here.

    Steps:
      1. department artifact → its resource id (via dept self-junction).
      2. department resource → ``setting_ids[0]`` (the setting resource id).
    """
    dept_arts = await get_department_artifacts(
        conn, [department_artifact_id], departments=True,
    )
    if not dept_arts or not dept_arts[0].department_ids:
        return None
    dept_resource_id = dept_arts[0].department_ids[0]

    dept_resources = await get_department_resources(conn, [dept_resource_id], redis)
    if not dept_resources or not dept_resources[0].setting_ids:
        return None
    return dept_resources[0].setting_ids[0]


async def generate_keycloak_theme_styles(pool: Any) -> None:
    """Generate ``login/theme-vars.ftl`` with per-department palettes.

    For each active department, resolves its setting's theme bundle
    (light + dark) and emits the 40-token palette into a FreeMarker
    map. ``head.ftl`` includes this file and renders ``:root{…}`` +
    dark-mode media query from the active department's palette.

    Forward-compat shape: even with one tenant, the file maps by
    dept_id. When per-org login skins arrive, no generator change
    needed — the template just picks the right entry.

    Empty-in / empty-out: settings that aren't active (or have no
    primary color) contribute no entry. ``head.ftl`` falls back to
    the hardcoded defaults in ``styles.css`` for any unmapped dept.
    """
    # Lazy import to avoid the circular ``identity.settings →
    # profile_identity_context → setting.search`` chain when this module
    # is imported.
    from app.infra.identity.settings import resolve_settings_theme
    from app.utils.settings.theme import derive_theme_tokens

    redis = get_redis_client()
    palettes: dict[str, dict[str, dict[str, str]]] = {}
    platform_palette: dict[str, dict[str, str]] | None = None

    async with pool.acquire() as conn:
        departments = await resolve_departments_for_sync(conn, redis)

    for dept in departments:
        async with pool.acquire() as conn:
            setting_resource_id = await _resolve_dept_setting_resource_id(
                conn, redis, dept.department_id,
            )
        if not setting_resource_id:
            continue
        # resolve_settings_theme accepts a setting *resource* id (the
        # canonical pointer carried on departments) and translates to
        # the owning artifact internally.
        theme = await resolve_settings_theme(pool, redis, setting_resource_id)
        if not theme or not theme.is_active or not theme.light.primary:
            continue
        light_tokens = derive_theme_tokens(theme.light).model_dump()
        dark_tokens = derive_theme_tokens(theme.dark).model_dump()
        palette = {
            "light": {k: v for k, v in light_tokens.items() if v},
            "dark": {k: v for k, v in dark_tokens.items() if v},
        }
        palettes[str(dept.department_id)] = palette
        # First non-empty palette becomes the "platform" default when no
        # department is selected (no URL param). Matches the
        # providers.ftl precedent: when departments exist, the first one
        # is the default.
        if platform_palette is None:
            platform_palette = palette

    # Write a plain CSS file (NOT a FreeMarker include). Keycloak's
    # template loader has surprising resolution rules when head.ftl is
    # invoked from the inherited template.ftl — a `<#include>` from a
    # child theme's head.ftl can silently fail. A static CSS file
    # linked via <link> from head.ftl is cache-safe and reliable.
    out_path = UPLOAD_FOLDER / "themes/glow/login/resources/css/theme-vars.css"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _kebab(name: str) -> str:
        return name.replace("_", "-")

    def _emit_root_block(tokens: dict[str, str]) -> list[str]:
        return [f"  --{_kebab(k)}: {v};" for k, v in tokens.items() if v]

    lines: list[str] = [
        "/* GENERATED FILE — do not edit manually. */",
        f"/* Generated at: {datetime.now().isoformat()} */",
        "/*",
        " * Theme tokens for the Keycloak login page. Bound to the",
        " * active setting's resolved ThemeBundle (light + dark) so the",
        " * login surface inherits the same brand palette as the",
        " * post-login dashboard.",
        " *",
        f" * {len(palettes)} department palette(s) embedded; one default at :root.",
        " */",
        "",
    ]

    if platform_palette:
        # Cascade strategy:
        #   1. `:root` → light tokens (always the default)
        #   2. `@media (prefers-color-scheme: dark) :root:not(.light)` →
        #      dark tokens when OS prefers dark AND user hasn't explicitly
        #      chosen light via the `.light` class.
        #   3. `:root.dark` → dark tokens always when user explicitly chose
        #      dark (placed LAST so it overrides the media query).
        #
        # A small <script> in login.ftl reads the `glow_theme` cookie (or
        # `?glow_theme=` URL param) and toggles `.light` / `.dark` on
        # <html>, mirroring how the Next.js app handles next-themes.
        lines.append(":root {")
        lines.extend(_emit_root_block(platform_palette["light"]))
        lines.append("}")
        lines.append("")
        dark_tokens = platform_palette["dark"]
        if any(dark_tokens.values()):
            # OS-preference dark mode (only when no explicit override)
            lines.append("@media (prefers-color-scheme: dark) {")
            lines.append("  :root:not(.light) {")
            lines.extend(
                f"    --{_kebab(k)}: {v};" for k, v in dark_tokens.items() if v
            )
            lines.append("  }")
            lines.append("}")
            lines.append("")
            # Explicit class override (Next.js next-themes parity)
            lines.append(":root.dark {")
            lines.extend(
                f"  --{_kebab(k)}: {v};" for k, v in dark_tokens.items() if v
            )
            lines.append("}")
            lines.append("")

    # Per-department scoped blocks (forward-compat: head.ftl can flip
    # the active palette by URL param via a `data-department-id`
    # attribute on <html>, similar to how providers.ftl is consumed).
    for dept_id, palette in palettes.items():
        lines.append(f'[data-department-id="{dept_id}"] {{')
        lines.extend(_emit_root_block(palette["light"]))
        lines.append("}")
        dark_tokens = palette["dark"]
        if any(dark_tokens.values()):
            lines.append("@media (prefers-color-scheme: dark) {")
            lines.append(f'  [data-department-id="{dept_id}"] {{')
            lines.extend(
                f"    --{_kebab(k)}: {v};" for k, v in dark_tokens.items() if v
            )
            lines.append("  }")
            lines.append("}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"✅ Generated theme styles: {out_path.resolve()}")
    logger.info(f"   - {len(palettes)} department palettes")
    logger.info(
        f"   - platform default: {'yes' if platform_palette else 'none (falls back to styles.css)'}"
    )


async def _resolve_login_entries(
    conn: Any,
    redis: Any,
    login_objects: list[LoginForSync],
) -> list[dict]:
    """Resolve login objects into entries with alias and icon_svg.

    For auth logins: alias = auth_{slug}_{auth_resource_id}
    For profile logins: alias = default-idp-profile-{profile_resource_id}
    Icon SVGs are fetched from icons_resource by icon_id.
    """
    if not login_objects:
        return []

    # Deduplicate logins by id
    seen_ids: set[UUID] = set()
    unique_logins: list[LoginForSync] = []
    for lg in login_objects:
        if lg.id not in seen_ids:
            seen_ids.add(lg.id)
            unique_logins.append(lg)

    # Collect all icon_ids and auth_ids to batch-fetch
    icon_ids: list[UUID] = []
    auth_ids: list[UUID] = []
    for lg in unique_logins:
        if lg.icon_id and lg.icon_id not in icon_ids:
            icon_ids.append(lg.icon_id)
        if lg.auth_id and lg.auth_id not in auth_ids:
            auth_ids.append(lg.auth_id)

    # Batch-fetch icons
    icon_svg_map: dict[UUID, str] = {}
    if icon_ids:
        try:
            icon_resources = await get_icons(conn, icon_ids, redis)
            for icon in icon_resources:
                icon_svg_map[icon.id] = icon.value or ""
        except Exception as e:
            logger.warning(f"Failed to fetch icons for login entries: {e}")

    # Batch-fetch auth resources for slug (to construct aliases)
    auth_slug_map: dict[UUID, str] = {}
    auth_resource_id_map: dict[UUID, UUID] = {}
    if auth_ids:
        try:
            auth_resources = await get_auth_resources(conn, auth_ids, redis)
            for a in auth_resources:
                auth_slug_map[a.id] = a.slug or ""
                auth_resource_id_map[a.id] = a.id
        except Exception as e:
            logger.warning(f"Failed to fetch auth resources for login entries: {e}")

    # Build entries
    entries: list[dict] = []
    for lg in unique_logins:
        # Determine alias
        if lg.login_type == "auth" and lg.auth_id:
            slug = auth_slug_map.get(lg.auth_id, "")
            alias = f"auth_{slug}_{lg.auth_id}"
        elif lg.login_type == "profile" and lg.profile_id:
            alias = f"default-idp-profile-{lg.profile_id}"
        else:
            # Unknown login type — skip
            continue

        icon_svg = icon_svg_map.get(lg.icon_id, "") if lg.icon_id else ""

        entries.append({
            "alias": alias,
            "display_name": lg.display_name,
            "icon_svg": icon_svg,
            "login_type": lg.login_type,
        })

    return entries
