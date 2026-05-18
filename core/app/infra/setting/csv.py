"""Setting CSV parse — accepts raw CSV bytes, auto-maps columns to import fields,
returns mapped items for client-side preview before bulk create.

Routes/setting/csv.py is a thin HTTP adapter over parse_setting_csv_impl.
"""

from __future__ import annotations

import csv
import io
import os
import uuid as uuid_mod
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.infra.setting.search import SETTING_IMPORT_FIELDS
from app.infra.setting.types import CreateSettingItem
from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.uploads.create import create_upload


class ParseSettingCsvApiResponse(BaseModel):
    """Response for CSV parse — mapped items ready for review."""

    upload_id: UUID
    items: list[CreateSettingItem]
    mapped_fields: list[str]
    row_count: int


class CsvParseError(ValueError):
    """Raised for client-side CSV errors (translate to 400 at the route boundary)."""


def _normalize(s: str) -> str:
    return s.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _build_field_map(headers: list[str]) -> dict[int, dict[str, Any]]:
    field_lookup: dict[str, dict[str, Any]] = {}
    for field in SETTING_IMPORT_FIELDS:
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


def _row_to_item(row: list[str], field_map: dict[int, dict[str, Any]]) -> CreateSettingItem:
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
    return CreateSettingItem(**kwargs)


async def parse_setting_csv_impl(
    pool: asyncpg.Pool,
    *,
    session_id: UUID,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    **_kwargs,
) -> ParseSettingCsvApiResponse:
    """Parse a CSV file and return mapped setting items for preview.

    Accepts pre-read bytes (``UploadFile`` must be read at the route boundary).
    Raises ``CsvParseError`` for any client-supplied invalid CSV — the route
    adapter translates that to a 400.
    """
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

    content = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    all_rows = list(reader)

    if len(all_rows) < 2:
        raise CsvParseError("CSV must have a header row and at least one data row")

    headers = all_rows[0]
    data_rows = all_rows[1:]

    field_map = _build_field_map(headers)
    if not field_map:
        labels = ", ".join(f["label"] for f in SETTING_IMPORT_FIELDS)
        raise CsvParseError(
            f"No CSV columns matched import fields. Expected: {labels}",
        )

    mapped_fields = [field_map[idx]["key"] for idx in sorted(field_map.keys())]

    required_keys = {f["key"] for f in SETTING_IMPORT_FIELDS if f.get("required")}
    mapped_keys = {f["key"] for f in field_map.values()}
    missing = required_keys - mapped_keys
    if missing:
        raise CsvParseError(f"Missing required columns: {', '.join(missing)}")

    items = [_row_to_item(row, field_map) for row in data_rows]

    return ParseSettingCsvApiResponse(
        upload_id=upload_result.id,
        items=items,
        mapped_fields=mapped_fields,
        row_count=len(data_rows),
    )
