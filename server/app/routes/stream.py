"""Stream delivery — GET /v5/stream (SSE) + POST /v5/stream/{Type} (OpenAPI schema).

Root-level transport route (not a v5 business action).

The SSE endpoint streams artifact events to clients.
Authorization is handled by the stream session: callers must first
POST /v5/connect to obtain an ``sid``, then POST /v5/attempt/join (or
/v5/test/join) to subscribe to specific entities.  The SSE endpoint
only delivers events matching joined entities.

The schema routes are dummy POST endpoints so ``openapi-typescript``
generates strongly-typed client payloads from EVENT_REGISTRY.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.infra.events.store import build_event_cursor, read_artifact_events
from app.infra.identity.middleware import require_auth
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.hub import subscribe as subscribe_live_events
from app.infra.stream.hub import unsubscribe as unsubscribe_live_events
from app.infra.stream.registry import EVENT_REGISTRY
from app.infra.stream.session import get_joined_entities, get_session_profile

# --- Socket types not yet modeled as artifact operations ----------------
from app.infra.test.client_types import (
    TestEndAllPayload,
    TestGroupPayload,
    TestJoinedEvent,
    TestJoinPayload,
    TestLeavePayload,
    TestNextPayload,
    TestRunDeltaEvent,
    TestRunPayload,
)
from app.infra.attempt.client_types import (
    AttemptAssistantHintsEvent,
    AttemptAudioStopPayload,
    AttemptEndAllPayload,
    AttemptErrorEvent,
    AttemptJoinedEvent,
    AttemptJoinPayload,
    AttemptLeavePayload,
    AttemptNextPayload,
    AttemptUsePreviousPayload,
    AttemptUserCompleteEvent,
    AttemptUserDeltaEvent,
    AttemptUserProgressEvent,
    AttemptUserStartEvent,
)
from app.infra.session.client_types import ConnectionConfirmedPayload
from app.infra.websocket.generation_types import (
    GeneratePayload,
    GenerationCompleteEvent,
    GenerationErrorEvent,
    GenerationMediaCompleteEvent,
    GenerationMediaProgressEvent,
    GenerationProgressEvent,
    GenerationSavedEvent,
)

router = APIRouter(
    prefix="/v5/stream",
    tags=["stream"],
    dependencies=[Depends(require_auth)],
)

# ---------------------------------------------------------------------------
# SSE endpoint — GET /v5/stream
# ---------------------------------------------------------------------------


@router.get("/")
async def stream_events(
    http_request: Request,
    sid: str = Query(...),
    cursor: str | None = Query(default=None),
    types: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> StreamingResponse:
    """Stream artifact events via SSE, scoped to the session's joined entities.

    Callers must first obtain an ``sid`` via POST /v5/connect, then join
    entities via POST /v5/attempt/join or POST /v5/test/join.  Only events
    matching joined entities are delivered.
    """
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    profile_id = UUID(str(profile_id))

    # Validate session ownership
    session_profile = await get_session_profile(sid)
    if not session_profile or session_profile != profile_id:
        raise HTTPException(status_code=403, detail="Session not found or not owned.")

    # Resolve joined entities for this session
    joined = await get_joined_entities(sid)
    if not joined:
        raise HTTPException(
            status_code=400,
            detail="No entities joined. Use /v5/attempt/join or /v5/test/join first.",
        )

    # Subscribe to live events for each joined entity
    type_filter = set(types) if types else None
    queues = []
    for key in joined:
        artifact, entity_id_str = key.split(":", 1)
        entity_id = UUID(entity_id_str)
        queue = subscribe_live_events(
            artifact=artifact,
            operation="*",
            entity_id=entity_id,
            event_types=types,
        )
        queues.append(queue)

    async def _gen() -> AsyncIterator[str]:
        current_cursor = cursor
        try:
            while True:
                # Read persisted events for all joined entities across all operations
                all_events = []
                pool = get_pool()
                redis = get_redis_client()
                for key in await get_joined_entities(sid):
                    artifact, entity_id_str = key.split(":", 1)
                    entity_id = UUID(entity_id_str)
                    config = EVENT_REGISTRY.get(artifact)
                    if not config:
                        continue
                    for operation in config.operations:
                        events = await read_artifact_events(
                            pool,
                            redis,
                            artifact=artifact,
                            operation=operation,
                            entity_id=entity_id,
                            cursor=current_cursor,
                            event_types=types,
                            limit=limit,
                        )
                        all_events.extend(events)

                # Sort by created_at for consistent ordering
                all_events.sort(key=lambda e: e.created_at)

                if all_events:
                    for event in all_events[:limit]:
                        current_cursor = build_event_cursor(event)
                        yield f"id: {event.id}\n"
                        yield f"event: {event.event_type}\n"
                        yield f"data: {event.model_dump_json()}\n\n"
                    continue

                # Wait for live events from any joined entity
                done = set()
                try:
                    wait_tasks = [
                        asyncio.ensure_future(q.get()) for q in queues
                    ]
                    done, pending = await asyncio.wait(
                        wait_tasks,
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                except TimeoutError:
                    pass

                if not done:
                    yield ": keep-alive\n\n"
                    continue

                for task in done:
                    event = task.result()
                    if type_filter and event.event_type not in type_filter:
                        continue
                    current_cursor = build_event_cursor(event)
                    yield f"id: {event.id}\n"
                    yield f"event: {event.event_type}\n"
                    yield f"data: {event.model_dump_json()}\n\n"
        finally:
            for q in queues:
                unsubscribe_live_events(q)

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# OpenAPI schema — POST /v5/stream/{ModelName}
# ---------------------------------------------------------------------------

_models: dict[str, type[BaseModel]] = {}
_model_tags: dict[str, str] = {}  # model name → parent router tag

# Mapping from EVENT_REGISTRY key (singular) to router tag (as in URL prefix)
_ARTIFACT_TAGS: dict[str, str] = {
    "activity": "activity",
    "agent": "agents",
    "attempt": "attempt",
    "auth": "auths",
    "benchmark": "benchmark",
    "chat": "chat",
    "cohort": "cohorts",
    "dashboard": "dashboard",
    "department": "departments",
    "document": "documents",
    "eval": "evals",
    "field": "fields",
    "group": "group",
    "health": "health",
    "home": "home",
    "invocation": "invocation",
    "leaderboard": "leaderboard",
    "model": "models",
    "parameter": "parameters",
    "persona": "personas",
    "pricing": "pricing",
    "practice": "practice",
    "profile": "profiles",
    "provider": "providers",
    "record": "record",
    "reports": "reports",
    "rubric": "rubrics",
    "scenario": "scenarios",
    "session": "session",
    "setting": "settings",
    "simulation": "simulations",
    "test": "test",
    "tool": "tools",
}


def _register(model: type[BaseModel] | None, tag: str | None = None) -> None:
    if model is not None and model.__name__ not in _models:
        _models[model.__name__] = model
        if tag:
            _model_tags[model.__name__] = tag


# 1. Artifact operations (EVENT_REGISTRY) — tag with parent router
for _artifact_key, _config in EVENT_REGISTRY.items():
    _tag = _ARTIFACT_TAGS.get(_artifact_key, _artifact_key)
    for _op in _config.operations.values():
        for _m in _op.lifecycle_models.values():
            _register(_m, tag=_tag)
        for _m in _op.domain_events.values():
            _register(_m, tag=_tag)

# 2. Socket types not yet in EVENT_REGISTRY — tag by prefix
_EXTRA_SOCKET_TYPES: list[type[BaseModel]] = [
    ConnectionConfirmedPayload,
    GeneratePayload,
    GenerationProgressEvent,
    GenerationCompleteEvent,
    GenerationErrorEvent,
    GenerationSavedEvent,
    GenerationMediaProgressEvent,
    GenerationMediaCompleteEvent,
    AttemptJoinPayload,
    AttemptLeavePayload,
    AttemptJoinedEvent,
    AttemptNextPayload,
    AttemptEndAllPayload,
    AttemptUsePreviousPayload,
    AttemptAudioStopPayload,
    AttemptErrorEvent,
    AttemptAssistantHintsEvent,
    AttemptUserStartEvent,
    AttemptUserProgressEvent,
    AttemptUserCompleteEvent,
    AttemptUserDeltaEvent,
    TestJoinPayload,
    TestLeavePayload,
    TestJoinedEvent,
    TestNextPayload,
    TestRunPayload,
    TestGroupPayload,
    TestEndAllPayload,
    TestRunDeltaEvent,
]

for _m in _EXTRA_SOCKET_TYPES:
    _name = _m.__name__
    if _name.startswith("Attempt"):
        _register(_m, tag="attempt")
    elif _name.startswith("Test"):
        _register(_m, tag="test")
    elif _name.startswith("Generation") or _name.startswith("Generate"):
        _register(_m, tag="group")
    elif _name.startswith("Connection"):
        _register(_m, tag="session")
    else:
        _register(_m)


def _make_endpoint(model: type[BaseModel]) -> Callable[..., Any]:
    async def endpoint(request: Any) -> dict[str, bool]:
        return {"success": True}

    endpoint.__name__ = f"{model.__name__}_schema"
    endpoint.__qualname__ = f"{model.__name__}_schema"
    endpoint.__annotations__["request"] = model
    endpoint.__annotations__["return"] = dict[str, bool]
    return endpoint


for _name, _model in sorted(_models.items()):
    _extra_tags = [_model_tags[_name]] if _name in _model_tags else []
    router.add_api_route(
        f"/{_name}",
        _make_endpoint(_model),
        methods=["POST"],
        tags=_extra_tags,
        name=f"{_name}_schema",
        summary=f"Schema: {_name}",
    )
