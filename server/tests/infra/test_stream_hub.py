from __future__ import annotations

import pytest
import pytest_asyncio

from app.infra.stream.emitter import emit_artifact_operation_events
from app.infra.stream.hub import subscribe, unsubscribe


@pytest.mark.asyncio
async def test_emit_artifact_operation_events_publishes_matching_live_event() -> None:
    queue = subscribe(artifact="persona", operation="create")
    try:
        await emit_artifact_operation_events(
            artifact="persona",
            operation="create",
            arguments={"personas": [{"name": "Live Persona"}]},
            output={
                "success": True,
                "results": [
                    {
                        "success": True,
                        "persona_id": "019ce726-fa14-7f2a-aebb-0067bca4b029",
                        "message": "ok",
                    }
                ],
            },
        )

        seen = []
        for _ in range(3):
            seen.append((await queue.get()).event_type)

        assert seen == [
            "artifacts.persona.create.started",
            "artifacts.persona.create.completed",
            "artifacts.persona.created",
        ]
    finally:
        unsubscribe(queue)
