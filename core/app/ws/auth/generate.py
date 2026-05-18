"""Input: auth.generate"""

from typing import Any

from app.infra.auth.generate import generate_auth_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.generation_types import (
    ArtifactGenerateRequest,
    GenerateConfig,
    GenerateErrorApiRequest,
)
from app.infra.websocket.typed_emit import emit_to_internal

internal_sio = get_internal_sio()


async def _emit_error(sid: str, message: str) -> None:
    await emit_to_internal(
        "auth.generate.error",
        GenerateErrorApiRequest(
            sid=sid,
            error_message=message,
            artifact_type="auth",
            resource_type="auth",
        ),
        sid=sid,
    )


@sio.on("auth.generate")  # type: ignore
async def auth_generate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        await _emit_error(sid, "Profile not found. Please reconnect.")
        return

    try:
        payload = ArtifactGenerateRequest(**data)
    except Exception as e:
        await _emit_error(sid, f"Invalid request: {str(e)}")
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="auth",
        operation="generate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: generate_auth_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            sid=sid,
            **payload.model_dump(exclude={'config'}, exclude_none=True),
            **(payload.config or GenerateConfig()).model_dump(exclude_none=True),
        ),
        arguments=payload.model_dump(mode="json"),
    )
