"""Chat export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_chat_context — draft-only resource hydration
  3. Flatten selected resources into denormalized CSV
  4. CSV generation + upload entry creation
"""

from __future__ import annotations

import base64
import csv
import io
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.chat.context import resolve_chat_context
from app.infra.profile_identity_context import resolve_profile_identity_context

PIPE = "|"

CSV_COLUMNS = [
    "chat_entry_id",
    "group_id",
    "draft_version",
    "name",
    "description",
    "active",
    "departments",
    "personas",
    "documents",
    "scenarios",
    "fields",
    "parameter_fields",
    "questions",
    "options",
    "videos",
    "images",
    "problem_statements",
    "objectives",
]


async def export_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    chat_entry_id: UUID,
    group_id: UUID,
    attempt_id: UUID | None = None,
    draft_id: UUID | None = None,
) -> dict:
    """Chat single-item export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. resolve_chat_context → draft-only hydrated resources
      3. Flatten selected resources into denormalized CSV row
      4. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.chat.types import ExportChatApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Resolve chat context (draft-only) ──────────────────────

    ctx = await resolve_chat_context(
        pool,
        redis,
        group_id=group_id,
        draft_id=draft_id,
    )

    # ── Step 3: Flatten selected resources into CSV row ─────────────────

    resources = ctx.resources

    # Single-select: first item's display value
    name = ""
    if resources.get("names") and resources["names"].selected:
        n = resources["names"].selected[0]
        name = getattr(n, "name", "") or ""

    description = ""
    if resources.get("descriptions") and resources["descriptions"].selected:
        d = resources["descriptions"].selected[0]
        description = getattr(d, "description", "") or ""

    # Active flag from flags
    active = "No"
    if resources.get("flags") and resources["flags"].selected:
        for f in resources["flags"].selected:
            if getattr(f, "name", "") == "chat_active":
                active = "Yes"
                break

    # Multi-select: pipe-delimited display values
    departments_str = PIPE.join(
        getattr(d, "name", "") or ""
        for d in (
            resources.get("departments", None)
            and resources["departments"].selected
            or []
        )
    )
    personas_str = PIPE.join(
        getattr(p, "name", "") or ""
        for p in (
            resources.get("personas", None) and resources["personas"].selected or []
        )
    )
    documents_str = PIPE.join(
        getattr(d, "name", "") or ""
        for d in (
            resources.get("documents", None) and resources["documents"].selected or []
        )
    )
    scenarios_str = PIPE.join(
        getattr(s, "name", "") or ""
        for s in (
            resources.get("scenarios", None) and resources["scenarios"].selected or []
        )
    )
    fields_str = PIPE.join(
        getattr(f, "name", "") or ""
        for f in (resources.get("fields", None) and resources["fields"].selected or [])
    )
    parameter_fields_str = PIPE.join(
        getattr(pf, "name", "") or ""
        for pf in (
            resources.get("parameter_fields", None)
            and resources["parameter_fields"].selected
            or []
        )
    )
    questions_str = PIPE.join(
        getattr(q, "question", "") or getattr(q, "name", "") or ""
        for q in (
            resources.get("questions", None) and resources["questions"].selected or []
        )
    )
    options_str = PIPE.join(
        getattr(o, "option", "") or getattr(o, "name", "") or ""
        for o in (
            resources.get("options", None) and resources["options"].selected or []
        )
    )
    videos_str = PIPE.join(
        getattr(v, "name", "") or ""
        for v in (resources.get("videos", None) and resources["videos"].selected or [])
    )
    images_str = PIPE.join(
        getattr(i, "name", "") or ""
        for i in (resources.get("images", None) and resources["images"].selected or [])
    )
    problem_statements_str = PIPE.join(
        getattr(ps, "statement", "") or getattr(ps, "name", "") or ""
        for ps in (
            resources.get("problem_statements", None)
            and resources["problem_statements"].selected
            or []
        )
    )
    objectives_str = PIPE.join(
        getattr(o, "objective", "") or getattr(o, "name", "") or ""
        for o in (
            resources.get("objectives", None) and resources["objectives"].selected or []
        )
    )

    # ── Step 4: Generate CSV + upload ──────────────────────────────────

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    writer.writerow(
        [
            str(chat_entry_id),
            str(group_id),
            str(ctx.draft_version or ""),
            name,
            description,
            active,
            departments_str,
            personas_str,
            documents_str,
            scenarios_str,
            fields_str,
            parameter_fields_str,
            questions_str,
            options_str,
            videos_str,
            images_str,
            problem_statements_str,
            objectives_str,
        ]
    )

    csv_content = output.getvalue()
    row_count = 1

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"chat_export_{timestamp}.csv"

    return ExportChatApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
