"""Typed WebSocket emit helpers."""

from typing import Any, TypeVar

from pydantic import BaseModel

from app.infra.globals import sio

T = TypeVar("T", bound=BaseModel)


async def emit_to_client(
    event_name: str,
    payload: T,
    room: str | None = None,
    *,
    sio_client: Any | None = None,
) -> None:
    """Emit typed event to client.

    Uses auto-generated types from SQL introspection for type safety.

    Args:
        event_name: Socket.IO event name (e.g., "rubrics_generation_complete")
        payload: Typed payload (e.g., RubricGenerationCompleteSqlRow)
        room: Socket ID or room name (defaults to empty string for broadcast)
    """
    active_sio = sio_client or sio
    await active_sio.emit(
        event_name,
        payload.model_dump(mode="json"),  # Serialize UUIDs to strings
        room=room or "",
    )


async def emit_to_internal(
    event_name: str,
    payload: T,
    sid: str | None = None,
    group_id: str | None = None,
    *,
    internal_bus: Any | None = None,
) -> None:
    """Emit typed event to internal bus (server-to-server).

    Adds sid and group_id for routing and grouping.

    Args:
        event_name: Internal event name (e.g., "rubric_complete")
        payload: Typed payload using target event's ApiRequest type
        sid: Socket ID for routing responses
        group_id: Group ID for grouping runs
    """
    from app.infra.globals import get_internal_sio

    active_internal_bus = internal_bus or get_internal_sio()
    emit_data: dict[str, Any] = {
        **payload.model_dump(mode="json"),
    }
    if sid:
        emit_data["sid"] = sid
    if group_id:
        emit_data["group_id"] = group_id

    await active_internal_bus.emit(event_name, emit_data)
