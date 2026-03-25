"""Input: scenario.get"""

from typing import Any
from uuid import UUID

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.get import get_scenario_impl
from app.infra.scenario.types import GetScenarioApiRequest

internal_sio = get_internal_sio()


@sio.on("scenario.get")  # type: ignore
async def scenario_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetScenarioApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("scenario.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="scenario",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            scenario_id=payload.scenario_id,
            draft_id=payload.draft_id,
            parameter_ids=[UUID(str(pid)) for pid in payload.parameter_ids]
            if payload.parameter_ids
            else None,
            description_search=payload.description_search,
            persona_search=payload.persona_search,
            document_search=payload.document_search,
            parameter_search=payload.parameter_search,
            problem_statement_search=payload.problem_statement_search,
            image_search=payload.image_search,
            video_search=payload.video_search,
            question_search=payload.question_search,
            option_search=payload.option_search,
            persona_show_selected=payload.persona_show_selected,
            document_show_selected=payload.document_show_selected,
            parameter_show_selected=payload.parameter_show_selected,
        ),
        arguments=payload.model_dump(mode="json"),
    )
