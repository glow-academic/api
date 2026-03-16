"""Naive event store backed by calls_entry + persisted call receipts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
from redis.asyncio import Redis

from app.events.types import build_lifecycle_event_type
from app.infra.tools.call_args import resolve_tool
from app.infra.stream.registry import get_artifact_events_config
from app.infra.stream.types import EventEnvelope
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.calls.search import search_calls
from app.tools.entries.uploads.get import get_upload
from app.utils.storage.file_writer import read_text_file

_FETCH_MULTIPLIER = 5


def _parse_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    """Parse the naive cursor format '{created_at}::{call_id}'."""
    if not cursor or "::" not in cursor:
        return None
    created_at_raw, call_id = cursor.split("::", 1)
    return (datetime.fromisoformat(created_at_raw), call_id)


def build_event_cursor(event: EventEnvelope) -> str:
    """Serialize an event cursor."""
    return f"{event.created_at.isoformat()}::{event.id}"


def _is_after_cursor(
    created_at: datetime,
    event_id: str,
    cursor: tuple[datetime, str] | None,
) -> bool:
    """Return True when an event sorts after the provided cursor."""
    if cursor is None:
        return True
    return (created_at, event_id) > cursor


def build_operation_events(
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None,
    created_at: datetime,
    call_id: UUID | None,
    tool_id: UUID | None,
    arguments: dict,
    output: dict,
) -> list[EventEnvelope]:
    """Project operation input/output into lifecycle + domain events."""
    config = get_artifact_events_config(artifact)
    if config is None:
        return []

    operation_config = config.get_operation(operation)
    if operation_config is None:
        return []

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = {"raw": output}

    success = not (isinstance(output, dict) and output.get("success") is False)
    events: list[EventEnvelope] = []
    domain_entity_ids: list[UUID]

    if operation_config.resolve_entity_ids is not None:
        try:
            domain_entity_ids = operation_config.resolve_entity_ids(
                arguments,
                output if isinstance(output, dict) else {},
            )
        except (TypeError, ValueError):
            domain_entity_ids = []
    elif entity_id is not None:
        domain_entity_ids = [entity_id]
    else:
        domain_entity_ids = []

    lifecycle_entity_id = entity_id
    if lifecycle_entity_id is None and len(domain_entity_ids) == 1:
        lifecycle_entity_id = domain_entity_ids[0]

    if operation_config.include_call_lifecycle:
        event_root = str(call_id or uuid4())
        started_event_type = build_lifecycle_event_type(artifact, operation, "started")
        events.append(
            EventEnvelope(
                id=f"{event_root}:{started_event_type}",
                event_type=started_event_type,
                artifact=artifact,
                operation=operation,
                created_at=created_at,
                entity_id=lifecycle_entity_id,
                call_id=call_id,
                tool_id=tool_id,
                payload={"arguments": arguments},
            )
        )
        lifecycle_type = build_lifecycle_event_type(
            artifact,
            operation,
            "completed" if success else "failed",
        )
        events.append(
            EventEnvelope(
                id=f"{event_root}:{lifecycle_type}",
                event_type=lifecycle_type,
                artifact=artifact,
                operation=operation,
                created_at=created_at,
                entity_id=lifecycle_entity_id,
                call_id=call_id,
                tool_id=tool_id,
                payload={"output": output},
            )
        )

    if (
        success
        and operation_config.project_domain_from_audit
        and len(operation_config.domain_event_names) == 1
    ):
        for event_type in operation_config.domain_event_names:
            target_entity_ids = domain_entity_ids or [entity_id]
            for target_entity_id in target_entity_ids:
                event_root = str(call_id or uuid4())
                events.append(
                    EventEnvelope(
                        id=f"{event_root}:{event_type}:{target_entity_id or 'collection'}",
                        event_type=event_type,
                        artifact=artifact,
                        operation=operation,
                        created_at=created_at,
                        entity_id=target_entity_id,
                        call_id=call_id,
                        tool_id=tool_id,
                        payload={
                            "arguments": arguments,
                            "output": output,
                        },
                    )
                )

    return events


def _project_call_receipt(
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None,
    created_at: datetime,
    call_id: UUID,
    tool_id: UUID | None,
    receipt: dict,
) -> list[EventEnvelope]:
    """Project a stored call receipt into lifecycle + domain events."""
    return build_operation_events(
        artifact=artifact,
        operation=operation,
        entity_id=entity_id,
        created_at=created_at,
        call_id=call_id,
        tool_id=tool_id,
        arguments=receipt.get("arguments") or {},
        output=receipt.get("output") or {},
    )


async def read_artifact_events(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None = None,
    cursor: str | None = None,
    event_types: list[str] | None = None,
    limit: int = 50,
) -> list[EventEnvelope]:
    """Read projected event envelopes from canonical tool-call receipts.

    TODO: Replace this naive receipt scan with a dedicated event store or
    call-progress/completion projection once that storage exists.
    """
    config = get_artifact_events_config(artifact)
    if config is None:
        return []

    operation_config = config.get_operation(operation)
    if operation_config is None:
        return []

    parsed_cursor = _parse_cursor(cursor)

    async with pool.acquire() as conn:
        tool_info = await resolve_tool(conn, operation, artifact, scope="artifacts")
        if tool_info is None:
            return []

        calls = await search_calls(
            conn,
            tool_ids=[tool_info.tool_id],
            limit=limit * _FETCH_MULTIPLIER,
            offset=0,
        )
        if not calls:
            return []

        call_ids = [call.call_id for call in calls]
        uploads = await search_call_uploads(
            conn,
            call_ids=call_ids,
            limit=len(call_ids) * 3,
            offset=0,
        )
        upload_by_call_id: dict[UUID, UUID] = {}
        for junction in uploads:
            upload = await get_upload(conn, junction.upload_id)
            if upload is None or upload.mime_type != "application/json":
                continue
            upload_by_call_id[junction.call_id] = upload.id

        upload_cache: dict[UUID, tuple[str, str]] = {}
        events: list[EventEnvelope] = []

        for call in reversed(calls):
            upload_id = upload_by_call_id.get(call.call_id)
            if upload_id is None:
                continue

            file_path: str
            mime_type: str
            if upload_id in upload_cache:
                file_path, mime_type = upload_cache[upload_id]
            else:
                upload = await get_upload(conn, upload_id)
                if upload is None:
                    continue
                file_path = upload.file_path
                mime_type = upload.mime_type
                upload_cache[upload_id] = (file_path, mime_type)

            if mime_type != "application/json" or not file_path.startswith("call/"):
                continue

            try:
                receipt = json.loads(read_text_file(file_path))
            except (OSError, json.JSONDecodeError):
                continue

            receipt_entity_id: UUID | None = None
            if operation_config.entity_key is not None:
                raw_entity_id = (receipt.get("arguments") or {}).get(
                    operation_config.entity_key
                )
                if raw_entity_id:
                    receipt_entity_id = UUID(str(raw_entity_id))

            if entity_id is not None and receipt_entity_id != entity_id:
                continue

            projected = _project_call_receipt(
                artifact=artifact,
                operation=operation,
                entity_id=receipt_entity_id,
                created_at=call.call_created_at,
                call_id=call.call_id,
                tool_id=call.tool_id,
                receipt=receipt,
            )

            for event in projected:
                if not _is_after_cursor(event.created_at, event.id, parsed_cursor):
                    continue
                if event_types and event.event_type not in event_types:
                    continue
                events.append(event)
                if len(events) >= limit:
                    return events

    return events
