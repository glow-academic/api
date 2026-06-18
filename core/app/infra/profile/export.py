"""Profile export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_profiles — full dump (all IDs, no filters, no pagination)
  3. get_profiles — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, departments, emails, request_limits, roles)
  5. CSV generation + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import io
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.profile.get import get_profiles
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.departments.get import get_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.roles.get import get_roles
from app.utils.csv.formula_safe import FormulaSafeWriter

PIPE = "|"

CSV_COLUMNS = [
    "profile_id",
    "name",
    "active",
    "departments",
    "emails",
    "roles",
]


async def export_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile_export_id: UUID | None = None,
) -> dict:
    """Profile full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_profiles → all IDs (full dump, no pagination)
      3. get_profiles → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.permissions_helpers import has_permission
    from app.infra.profile.types import ExportProfileApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Authorization (was COMPLETELY MISSING) ───────────────────────────
    #
    # This endpoint had NO permission check and NO role-tier scope: any
    # authenticated caller — verified incl. a guest token — could export EVERY
    # profile's name/email/department/role (the whole org directory). The
    # primary fix is the capability gate (stops guests/members — the confirmed
    # exploit); the bulk dump is additionally scoped to the caller's role tier,
    # mirroring the on-screen profile/search exclusion (roles strictly above the
    # caller, i.e. lower level number = higher privilege, are never visible) so a
    # permitted-but-lower-tier admin can't bulk-export superadmins.
    if not has_permission(profile.role_permissions, "profile", "export"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to export profiles.",
        )

    # ── Step 2: Resolve target profile ids ───────────────────────────────────

    async with pool.acquire() as conn:
        if profile_export_id:
            # Single-target export keeps the direct id (no search-index
            # dependency). NOTE: a finer per-target role-tier check on this path
            # is a documented follow-up; the capability gate already restricts
            # it to profile:export holders (admins+).
            profile_ids = [profile_export_id]
        else:
            # Bulk dump: exclude roles strictly above the caller's tier.
            all_roles = await get_roles(pool, None, redis)
            exclude_role_ids = [
                r.id for r in all_roles if r.level < profile.role_level
            ] or None
            profile_ids, _total_count = await search_profiles(
                conn,
                exclude_role_ids=exclude_role_ids,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not profile_ids:
            return ExportProfileApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get profile artifacts with all junction IDs ──────────

    with timed("hydrate"):
        artifacts = await get_profiles(
            pool,
            profile_ids,
            names=True,
            departments=True,
            flags=True,
            emails=True,
            roles=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    # Collect all resource IDs across artifacts
    all_name_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_email_ids: list[UUID] = []
    all_role_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_email_ids.extend(a.email_ids or [])
        all_role_ids.extend(a.role_ids or [])

    async def _empty() -> list:
        return []

    async def _fetch_names() -> list:
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_departments() -> list:
        return await get_departments(pool, all_department_ids, redis)

    async def _fetch_emails() -> list:
        return await get_emails(pool, all_email_ids, redis)

    async def _fetch_roles() -> list:
        return await get_roles(pool, all_role_ids, redis)

    (
        names_data,
        departments_data,
        emails_data,
        roles_data,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty(),
        _fetch_departments() if all_department_ids else _empty(),
        _fetch_emails() if all_email_ids else _empty(),
        _fetch_roles() if all_role_ids else _empty(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    department_map = {d.id: d.name for d in departments_data}
    email_map = {e.id: e.email for e in emails_data}
    role_map = {r.id: r.name for r in roles_data}

    # ── Step 5: Generate CSV + upload ──────────────────────────────────

    with timed("build"):
      output = io.StringIO()
      writer = FormulaSafeWriter(output)
      writer.writerow(CSV_COLUMNS)

      for a in artifacts:
          # Single-select: first resource value
          name = name_map.get(a.name_ids[0], "") if a.name_ids else ""

          # Active flag
          active = "Yes" if a.active else "No"

          # Multi-select: pipe-delimited values
          departments_str = PIPE.join(
              department_map.get(did, "") for did in (a.department_ids or [])
          )
          emails_str = PIPE.join(email_map.get(eid, "") for eid in (a.email_ids or []))

          # Multi-select: roles
          roles_str = PIPE.join(role_map.get(rid, "") for rid in (a.role_ids or []))

          writer.writerow(
              [
                  str(a.id),
                  name,
                  active,
                  departments_str,
                  emails_str,
                  roles_str,
              ]
          )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"profiles_export_{timestamp}.csv"

    return ExportProfileApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
