"""Persona CSV parse logic — composable infra architecture.

Accepts raw CSV bytes, auto-maps columns to persona import fields,
and returns mapped items for client-side preview before bulk create.

Flow:
  1. Save file to disk + create upload entry
  2. Parse CSV, auto-map headers to import fields
  3. Validate required columns present
  4. Convert rows to CreatePersonaItem list
"""

from __future__ import annotations

import csv
import io
import os
import uuid as uuid_mod
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.infra.globals import UPLOAD_FOLDER
from app.infra.persona.search import PERSONA_IMPORT_FIELDS
from app.infra.persona.types import CreatePersonaItem
from app.tools.entries.uploads.create import create_upload

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class ParsePersonaCsvApiResponse(BaseModel):
    """Response for CSV parse — mapped items ready for review."""

    upload_id: UUID = Field(..., description="UUID of the uploaded CSV file")
    items: list[CreatePersonaItem] = Field(..., description="Parsed persona items for preview")
    mapped_fields: list[str] = Field(..., description="Column keys that were auto-mapped")
    row_count: int = Field(..., description="Number of data rows parsed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    return s.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _get_import_fields_as_dicts() -> list[dict[str, Any]]:
    """Convert PERSONA_IMPORT_FIELDS (Pydantic models) to dicts for field mapping."""
    return [f.model_dump() for f in PERSONA_IMPORT_FIELDS]


def _build_field_map(headers: list[str]) -> dict[int, dict[str, Any]]:
    fields = _get_import_fields_as_dicts()
    field_lookup: dict[str, dict[str, Any]] = {}
    for field in fields:
        field_lookup[_normalize(field["key"])] = field
        field_lookup[_normalize(field["label"])] = field
    mapping: dict[int, dict[str, Any]] = {}
    for idx, header in enumerate(headers):
        norm = _normalize(header)
        if norm in field_lookup:
            mapping[idx] = field_lookup[norm]
    return mapping


def _parse_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in ("true", "yes", "1", "active"):
        return True
    if v in ("false", "no", "0", "inactive"):
        return False
    return None


def _row_to_item(row: list[str], field_map: dict[int, dict[str, Any]]) -> CreatePersonaItem:
    kwargs: dict[str, Any] = {}
    for col_idx, field_def in field_map.items():
        if col_idx >= len(row):
            continue
        raw = row[col_idx].strip()
        if not raw:
            continue
        key = field_def["key"]
        is_multi = field_def.get("multi", False)
        field_type = field_def.get("type", "string")
        if field_type == "boolean":
            kwargs[key] = _parse_bool(raw)
        elif is_multi:
            kwargs[key] = [v.strip() for v in raw.split(",") if v.strip()]
        else:
            kwargs[key] = raw
    return CreatePersonaItem(**kwargs)


# ---------------------------------------------------------------------------
# Impl
# ---------------------------------------------------------------------------


async def parse_persona_csv_impl(
    pool: asyncpg.Pool,
    *,
    session_id: UUID,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    **_kwargs,
) -> ParsePersonaCsvApiResponse:
    """Parse a CSV file and return mapped persona items for preview.

    Accepts pre-read bytes (UploadFile must be read at the route boundary).
    """
    # ── Step 1: Save to disk + create upload entry ────────────────────

    upload_uuid = uuid_mod.uuid4()
    ext = os.path.splitext(file_name)[1] or ".csv"
    relative_path = f"{upload_uuid}{ext}"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(file_bytes)

    async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            session_id=session_id,
            file_path=relative_path,
            mime_type=content_type,
            size=len(file_bytes),
        )

    # ── Step 2: Parse CSV ─────────────────────────────────────────────

    content = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    all_rows = list(reader)

    if len(all_rows) < 2:
        raise HTTPException(
            status_code=400,
            detail="CSV must have a header row and at least one data row",
        )

    headers = all_rows[0]
    data_rows = all_rows[1:]

    # ── Step 3: Auto-map columns ──────────────────────────────────────

    field_map = _build_field_map(headers)
    if not field_map:
        import_fields_dicts = _get_import_fields_as_dicts()
        raise HTTPException(
            status_code=400,
            detail="No CSV columns matched import fields. "
            f"Expected: {', '.join(f['label'] for f in import_fields_dicts)}",
        )

    mapped_fields = [field_map[idx]["key"] for idx in sorted(field_map.keys())]

    import_fields_dicts = _get_import_fields_as_dicts()
    required_keys = {f["key"] for f in import_fields_dicts if f.get("required")}
    mapped_keys = {f["key"] for f in field_map.values()}
    missing = required_keys - mapped_keys
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing)}",
        )

    # ── Step 4: Convert rows to items ─────────────────────────────────

    items = [_row_to_item(row, field_map) for row in data_rows]

    return ParsePersonaCsvApiResponse(
        upload_id=upload_result.id,
        items=items,
        mapped_fields=mapped_fields,
        row_count=len(data_rows),
    )
