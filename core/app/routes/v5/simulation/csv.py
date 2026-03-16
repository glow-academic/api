"""Simulation CSV parse endpoint — accepts a CSV file and returns mapped items for preview."""

from __future__ import annotations

import csv
import io
import os
import uuid as uuid_mod
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.infra.simulation.create import CreateSimulationItem
from app.infra.simulation.search import SIMULATION_IMPORT_FIELDS
from app.tools.entries.uploads.create import create_upload
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class ParseSimulationCsvApiResponse(BaseModel):
    """Response for CSV parse — mapped items ready for review."""

    upload_id: UUID
    items: list[CreateSimulationItem]
    mapped_fields: list[str]
    row_count: int


def _normalize(s: str) -> str:
    return s.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _build_field_map(headers: list[str]) -> dict[int, dict[str, Any]]:
    field_lookup: dict[str, dict[str, Any]] = {}
    for field in SIMULATION_IMPORT_FIELDS:
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


def _row_to_item(row: list[str], field_map: dict[int, dict[str, Any]]) -> CreateSimulationItem:
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
    return CreateSimulationItem(**kwargs)


@router.post("/csv", response_model=ParseSimulationCsvApiResponse)
async def parse_simulation_csv(
    file: UploadFile,
    http_request: Request,
) -> ParseSimulationCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        session_id = http_request.state.session_id
        pool = get_pool()

        # 1. Read file
        file_bytes = await file.read()

        # 2. Save to disk + create upload entry
        upload_uuid = uuid_mod.uuid4()
        ext = os.path.splitext(file.filename or "file.csv")[1] or ".csv"
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
                mime_type=file.content_type or "text/csv",
                size=len(file_bytes),
            )

        # 3. Parse CSV
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

        # 4. Auto-map columns
        field_map = _build_field_map(headers)
        if not field_map:
            raise HTTPException(
                status_code=400,
                detail="No CSV columns matched import fields. "
                f"Expected: {', '.join(f['label'] for f in SIMULATION_IMPORT_FIELDS)}",
            )

        mapped_fields = [field_map[idx]["key"] for idx in sorted(field_map.keys())]

        required_keys = {f["key"] for f in SIMULATION_IMPORT_FIELDS if f.get("required")}
        mapped_keys = {f["key"] for f in field_map.values()}
        missing = required_keys - mapped_keys
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )

        # 5. Convert to items
        items = [_row_to_item(row, field_map) for row in data_rows]

        return ParseSimulationCsvApiResponse(
            upload_id=upload_result.id,
            items=items,
            mapped_fields=mapped_fields,
            row_count=len(data_rows),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="parse_simulation_csv",
            request=http_request,
        )
