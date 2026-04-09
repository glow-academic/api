"""Output: generate_prepare — forwards to client AND runs the prepare pipeline."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.generate_prepare_impl import (
    generate_prepare_impl,
    resolve_primary_artifact_type,
)
from app.infra.websocket.socket_event import make_emit
from app.registry.generate import REGISTRY

internal_sio = get_internal_sio()


@internal_sio.on("generate_prepare")  # type: ignore
async def generate_prepare_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "generate_prepare", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("generate_prepare", data, room=room)

    # Run the prepare pipeline: resolve tools, dispatch to AI
    artifact_type = resolve_primary_artifact_type(data)
    artifact_config = REGISTRY.get(artifact_type)
    pool = get_pool()
    redis = get_redis_client()

    async with pool.acquire() as conn:
        await generate_prepare_impl(
            data,
            emit=make_emit(),
            pool=pool,
            conn=conn,
            redis=redis,
            artifact_config=artifact_config,
        )
