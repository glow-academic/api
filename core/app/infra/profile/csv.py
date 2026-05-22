"""Profile CSV parse — accepts raw CSV bytes, auto-maps columns to import fields,
returns mapped items for client-side preview before bulk create.

Routes/profile/csv.py is a thin HTTP adapter over parse_profile_csv_impl.
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

from app.infra.profile.search import PROFILE_IMPORT_FIELDS
from app.infra.profile.types import CreateProfileItem
from app.infra.globals import UPLOAD_FOLDER, get_redis_client
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.infra.activate.activate import activate_rows
from app.infra.server_timing import timed


class ParseProfileCsvApiResponse(BaseModel):
    """Response for CSV parse — mapped items ready for review."""

    upload_id: UUID
    items: list[CreateProfileItem]
    mapped_fields: list[str]
    row_count: int
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with `accept` to promote/reject the staged raw-CSV upload. NOTE: ack returns no items (the preview is only on the propose).")


class CsvParseError(ValueError):
    """Raised for client-side CSV errors (translate to 400 at the route boundary)."""


def _normalize(s: str) -> str:
    return s.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _build_field_map(headers: list[str]) -> dict[int, dict[str, Any]]:
    field_lookup: dict[str, dict[str, Any]] = {}
    for field in PROFILE_IMPORT_FIELDS:
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


def _row_to_item(row: list[str], field_map: dict[int, dict[str, Any]]) -> CreateProfileItem:
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
    return CreateProfileItem(**kwargs)


async def parse_profile_csv_impl(
    pool: asyncpg.Pool,
    *,
    session_id: UUID,
    file_bytes: bytes | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **_kwargs,
) -> ParseProfileCsvApiResponse:
    """Parse a CSV file and return mapped profile items for preview.

    Accepts pre-read bytes (``UploadFile`` must be read at the route boundary).
    Raises ``CsvParseError`` for any client-supplied invalid CSV — the route
    adapter translates that to a 400.
    """
    redis = get_redis_client()

    # ── Short-circuit: ack path — promote/reject the staged raw-CSV upload ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact="profile")
        if entry is None or entry.status != "pending" or entry.operation != "csv":
            raise HTTPException(
                status_code=404, detail="No pending CSV upload for this call.",
            )
        ids = entry.patch or {}
        if accept:
            async with pool.acquire() as conn:
                await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact="profile",
                operation="csv", artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return ParseProfileCsvApiResponse(
            upload_id=entry.artifact_id,
            items=[],
            mapped_fields=list(ids.get("mapped_fields", [])),
            row_count=int(ids.get("row_count", 0)),
            idempotency_key=idempotency_key,
        )

    if file_bytes is None or not file_name:
        raise HTTPException(
            status_code=400,
            detail="A CSV file is required (or pass `idempotency_key` + `accept` for the ack call).",
        )
    upload_uuid = uuid_mod.uuid4()
    ext = os.path.splitext(file_name)[1] or ".csv"
    relative_path = f"{upload_uuid}{ext}"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(file_bytes)

    with timed("db_write"):
      async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            redis,
            session_id=session_id,
            file_path=relative_path,
            mime_type=content_type,
            size=len(file_bytes),
            soft=soft,
        )

    content = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    all_rows = list(reader)

    if len(all_rows) < 2:
        raise CsvParseError("CSV must have a header row and at least one data row")

    headers = all_rows[0]
    data_rows = all_rows[1:]

    field_map = _build_field_map(headers)
    if not field_map:
        labels = ", ".join(f["label"] for f in PROFILE_IMPORT_FIELDS)
        raise CsvParseError(
            f"No CSV columns matched import fields. Expected: {labels}",
        )

    mapped_fields = [field_map[idx]["key"] for idx in sorted(field_map.keys())]

    required_keys = {f["key"] for f in PROFILE_IMPORT_FIELDS if f.get("required")}
    mapped_keys = {f["key"] for f in field_map.values()}
    missing = required_keys - mapped_keys
    if missing:
        raise CsvParseError(f"Missing required columns: {', '.join(missing)}")

    with timed("build"):
        items = [_row_to_item(row, field_map) for row in data_rows]

    # Soft: stash the raw upload as a pending soft_call (keyed by the server
    # call_id) so the ack can activate it. The preview above is returned now.
    if soft and call_id is not None:
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=call_id, artifact="profile",
                operation="csv", artifact_id=upload_result.id, status="pending",
                patch={
                    "upload_id": str(upload_result.id),
                    "mapped_fields": mapped_fields,
                    "row_count": len(data_rows),
                },
            )

    return ParseProfileCsvApiResponse(
        upload_id=upload_result.id,
        items=items,
        mapped_fields=mapped_fields,
        row_count=len(data_rows),
        idempotency_key=call_id,
    )
