"""Shared Pydantic types used across route layers.

These were previously auto-generated in app.sql.types — now hand-maintained.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bulk-write guard rail
# ---------------------------------------------------------------------------
# Upper bound on the number of items a single bulk create/update request may
# carry. Each item fans out into multiple per-item DB round trips (value
# resolution + snapshot + junction writes, several inside one transaction), so
# an unbounded list lets one authenticated request exhaust the connection pool
# / hold a transaction open arbitrarily long (resource-exhaustion DoS). Pydantic
# rejects oversized lists with a 422 before any DB work runs. Generous enough
# for legitimate CSV imports; the CSV import flow proposes items the client
# re-submits through these same bulk endpoints.
MAX_BULK_ITEMS = 500

# ---------------------------------------------------------------------------
# CSV-import parse guard rail
# ---------------------------------------------------------------------------
# Upper bound on the number of rows a single uploaded CSV may carry. The CSV
# parse path used to materialize the whole file (``list(csv.reader(...))``)
# before any size check, so a huge upload could spike memory during parse —
# even though the items it proposes are then re-submitted through the
# ``MAX_BULK_ITEMS``-capped bulk-create endpoints. We cap the row count at the
# same bound (a CSV that would exceed the create cap anyway is rejected early)
# plus the one mandatory header row, and we bail *while reading* rather than
# after materializing, so the unbounded read never happens.
MAX_CSV_ROWS = MAX_BULK_ITEMS + 1


def read_csv_rows_bounded(
    csv_file: Any,
    *,
    make_error: Callable[[str], Exception] | None = None,
    max_rows: int = MAX_CSV_ROWS,
) -> list[list[str]]:
    """Read a CSV file-like into rows, bailing as soon as ``max_rows`` is
    exceeded.

    Replaces the unbounded ``list(csv.reader(...))`` idiom: rows are pulled one
    at a time and the read aborts the moment the cap is crossed, so an
    oversized upload cannot be fully materialized in memory before being
    rejected. ``make_error`` lets each artifact raise its own client-CSV error
    type (e.g. ``CsvParseError`` or ``HTTPException``) — it receives the message
    and returns the exception to raise; defaults to ``ValueError``. The route
    boundary translates the raised error to a 4xx.
    """
    if make_error is None:
        make_error = ValueError
    reader = csv.reader(csv_file)
    rows: list[list[str]] = []
    for row in reader:
        if len(rows) >= max_rows:
            raise make_error(
                f"CSV exceeds the maximum of {max_rows - 1} data rows "
                f"(including a header row, {max_rows} lines). Split the import "
                f"into smaller files."
            )
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Upload-size guard rail
# ---------------------------------------------------------------------------
# Upper bound on the byte size of a single uploaded file (audio/image/document/
# CSV). The upload routes used to materialize the whole body with a single
# ``await file.read()`` *before* any size check — so an authenticated client
# could stream a multi-GB body and exhaust server memory (and then disk, since
# the bytes are written out) before anything rejected it (resource-exhaustion
# DoS). ``read_upload_bounded`` closes that gap: it pulls the body in chunks and
# aborts the moment the cap is crossed, so the oversized read never completes.
# 64 MiB is generous for the largest legitimate uploads (audio recordings,
# images) while keeping a hard ceiling on per-request memory.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

# Tighter ceiling for CSV imports specifically. A CSV import is plain text whose
# rows are already row-capped at ``MAX_CSV_ROWS`` (a few hundred rows) and then
# re-submitted through the ``MAX_BULK_ITEMS``-capped bulk endpoints, so a
# legitimate import is far smaller than a media upload. 16 MiB is well above any
# real import while bounding the bytes the parser ever holds — the byte-cap
# (this) runs first, the row-cap (``read_csv_rows_bounded``) second.
MAX_CSV_UPLOAD_BYTES = 16 * 1024 * 1024


async def read_upload_bounded(
    upload: Any,
    *,
    make_error: Callable[[str], Exception] | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    """Read a Starlette/FastAPI ``UploadFile`` fully, bailing as soon as
    ``max_bytes`` is exceeded.

    Replaces the unbounded ``await file.read()`` idiom: the body is pulled one
    chunk at a time and the read aborts the moment the cumulative size crosses
    the cap, so an oversized upload cannot be fully materialized in memory (or
    written to disk) before being rejected. ``make_error`` lets the caller raise
    its own client-facing error type (e.g. ``HTTPException(413)``) — it receives
    the message and returns the exception to raise; defaults to ``ValueError``.
    The route boundary translates the raised error to a 4xx.
    """
    if make_error is None:
        make_error = ValueError
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise make_error(
                f"Upload exceeds the maximum size of {max_bytes} bytes "
                f"({max_bytes // (1024 * 1024)} MiB). Upload a smaller file."
            )
        chunks.append(chunk)
    return b"".join(chunks)

# ---------------------------------------------------------------------------
# Profile context types
# ---------------------------------------------------------------------------


class QGetProfileContextV4RoleResource(BaseModel):
    role: str | None = None
    name: str | None = None
    description: str | None = None
    icon_value: str | None = None
    color_hex: str | None = None


class QGetProfileContextV4Department(BaseModel):
    department_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    active: bool | None = None


class QGetProfileContextV4Cohort(BaseModel):
    cohort_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    active: bool | None = None
    department_ids: list[str] | None = None


class QGetProfileContextV4ThemeTokens(BaseModel):
    background: str | None = None
    foreground: str | None = None
    card: str | None = None
    card_foreground: str | None = None
    popover: str | None = None
    popover_foreground: str | None = None
    primary_color: str | None = None
    primary_foreground: str | None = None
    secondary: str | None = None
    secondary_foreground: str | None = None
    muted: str | None = None
    muted_foreground: str | None = None
    accent: str | None = None
    accent_foreground: str | None = None
    destructive: str | None = None
    border: str | None = None
    input: str | None = None
    ring: str | None = None
    success: str | None = None
    success_foreground: str | None = None
    warning: str | None = None
    warning_foreground: str | None = None
    info: str | None = None
    info_foreground: str | None = None
    chart1: str | None = None
    chart2: str | None = None
    chart3: str | None = None
    chart4: str | None = None
    chart5: str | None = None
    sidebar: str | None = None
    sidebar_foreground: str | None = None
    sidebar_primary: str | None = None
    sidebar_primary_foreground: str | None = None
    sidebar_accent: str | None = None
    sidebar_accent_foreground: str | None = None
    sidebar_border: str | None = None
    sidebar_ring: str | None = None


# ---------------------------------------------------------------------------
# Department / Cohort resource types
# ---------------------------------------------------------------------------


class QGetDepartmentsV4Item(BaseModel):
    department_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None


class QGetCohortsV4Item(BaseModel):
    cohort_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    active: bool | None = None
    department_ids: list[str] | None = None
    profile_ids: list[str] | None = None
    profile_persona_ids: list[str] | None = None
    simulation_position_ids: list[str] | None = None
    simulation_availability_ids: list[str] | None = None


# ---------------------------------------------------------------------------
# Settings types
# ---------------------------------------------------------------------------


class QGetSettingsV4Auth(BaseModel):
    auth_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    slug: str | None = None


class QGetSettingsV4Item(BaseModel):
    settings_id: str | None = None
    created_at: datetime | None = None
    active: bool | None = None
    name: str | None = None
    description: str | None = None
    primary_color: str | None = None
    accent: str | None = None
    background: str | None = None
    surface: str | None = None
    success: str | None = None
    warning: str | None = None
    error: str | None = None
    sidebar_background: str | None = None
    sidebar_primary: str | None = None
    chart1: str | None = None
    chart2: str | None = None
    chart3: str | None = None
    chart4: str | None = None
    chart5: str | None = None
    guest_login_enabled: bool | None = None
    success_threshold: int | None = None
    warning_threshold: int | None = None
    danger_threshold: int | None = None
    auth_ids: list[str] | None = None
    auths: list[QGetSettingsV4Auth] | None = None
    provider_key_ids: list[UUID] | None = None


# ---------------------------------------------------------------------------
# Config chain types (agents, systems, models, providers, tools, args)
# ---------------------------------------------------------------------------


class QGetSystemsV4Item(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    agent_ids: list[UUID] | None = None
    active: bool | None = None
    generated: bool | None = None


class QGetAgentsV4Item(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    model_id: UUID | None = None
    temperature: float | None = None
    reasoning: str | None = None
    tool_ids: list[UUID] | None = None
    quality: str | None = None
    voices: list[str] | None = None
    prompt_id: UUID | None = None
    instruction_ids: list[UUID] | None = None
    active: bool | None = None
    generated: bool | None = None


class QGetModelsV4Item(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    provider_id: UUID | None = None
    modality_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None
    active: bool | None = None
    generated: bool | None = None


class QGetProvidersV4Item(BaseModel):
    id: UUID | None = None
    value: str | None = None
    name: str | None = None
    description: str | None = None
    endpoint: str | None = None
    key: str | None = None
    active: bool | None = None
    generated: bool | None = None


class QGetToolsV4Item(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None
    args_ids: list[UUID] | None = None
    args_output_ids: list[UUID] | None = None
    operation: str | None = None
    resources: list[str] | None = None
    entries: list[str] | None = None
    artifacts: list[str] | None = None


class QGetArgsV4Item(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    field_type: str | None = None
    required: bool | None = None
    default_value: str | None = None
    generated: bool | None = None


class QGetArgsOutputsV4Item(BaseModel):
    id: UUID | None = None
    args_id: UUID | None = None
    name: str | None = None
    template: str | None = None
    generated: bool | None = None


class QGetProfilesV4Item(BaseModel):
    profile_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    emails: list[str] | None = None
    primary_email: str | None = None
    request_limit: int | None = None


# ---------------------------------------------------------------------------
# Tool config type (used by generation infra)
# ---------------------------------------------------------------------------


class IGetTextRunContextAndCreateRunV4Tool(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    tool_type: str | None = None
    agent_role: str | None = None
    arguments: Any | None = None
    argument_descriptions: Any | None = None
    argument_defaults: Any | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Auth route request/response types
# ---------------------------------------------------------------------------


class GetProfileContextApiRequest(BaseModel):
    department_id: str | None = None
