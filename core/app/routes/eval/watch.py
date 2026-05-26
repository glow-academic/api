"""GET /eval/watch — live SSE endpoint (replaces /eval/stream).

GET + SSE is fixed at the HTTP boundary so browser ``EventSource`` works.
LLM tools dispatch to ``watch_eval_impl`` (one-shot) via INFRA_OPS, not
through this route. Same event hub feeds both consumers.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.infra._watch import WatchApiRequest, WatchApiResponse
from app.infra.eval.stream import stream_eval_impl
from app.infra.eval.watch import watch_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.get("/watch")
async def eval_watch(
    http_request: Request,
    group_id: UUID | None = Query(default=None),
    run_id: UUID | None = Query(
        default=None,
        description=(
            "Optional run filter. If provided, only events whose envelope "
            "run_id matches are streamed. Omit to receive every eval event "
            "in the group (the FE default)."
        ),
    ),
) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    return await stream_eval_impl(
        get_pool(), get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        run_id=run_id,
    )


@router.post("/watch", response_model=WatchApiResponse)
async def eval_watch_once(
    request: WatchApiRequest,
    http_request: Request,
) -> WatchApiResponse:
    """One-shot snapshot of run state, snapshot-replayable via ``snapshot_key``."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    pool = get_pool()
    redis = get_redis_client()

    async def _runner() -> WatchApiResponse:
        return await watch_eval_impl(
            pool,
            redis,
            profile_id=UUID(str(profile_id)),
            session_id=session_id,
            group_id=request.group_id,
            run_id=request.run_id,
            wait_for_complete=request.wait_for_complete,
            timeout_seconds=request.timeout_seconds,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="eval",
        profile_id=profile_id,
        session_id=session_id,
        group_id=request.group_id,
        operation="watch",
        arguments=request.model_dump(mode="json"),
        response_model=WatchApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
    )
