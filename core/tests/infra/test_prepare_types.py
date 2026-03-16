"""Tests for generation preparation and event type helpers."""

from uuid import uuid4

from app.infra.websocket.generation_types import (
    GeneratePayload,
    GenerationCompleteData,
)
from app.infra.websocket.prepare_types import (
    AgentDispatch,
    LLMConfig,
    MessageSpec,
    PreparedGeneration,
)
from app.infra.websocket.store_active_run import (
    generate_active_run_id,
    store_active_run,
)


def test_agent_dispatch_formats_messages_for_llm():
    dispatch = AgentDispatch(
        agent_id=uuid4(),
        resource_types=["documents"],
        entry_types=["messages"],
        messages=[
            MessageSpec(role="system", content="sys", raw_text="sys"),
            MessageSpec(role="user", content=[{"type": "input_text"}], raw_text="u"),
        ],
        llm_config=LLMConfig(
            model="gpt-test",
            api_key="key",
            base_url="https://example.com",
            temperature=0.2,
            reasoning=None,
            provider="openai",
            voice=None,
            quality=None,
        ),
        scoped_tools=[],
        metadata={},
    )

    assert dispatch.messages_for_llm == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": [{"type": "input_text"}]},
    ]


def test_prepared_generation_num_agents_counts_dispatches():
    prepared = PreparedGeneration(
        artifact_type="document",
        run_id=uuid4(),
        group_id=uuid4(),
        session_id=uuid4(),
        profile_id=uuid4(),
        artifact_id=None,
        draft_id=None,
        sid="sid-1",
        save=True,
        modality="text",
        resource_types=["documents"],
        agent_ids_for_run=[uuid4(), uuid4()],
        dispatches=[],
    )

    assert prepared.num_agents == 0


def test_generate_payload_coerces_string_resource_types_and_exposes_primary_type():
    payload = GeneratePayload(
        artifact_types=[{"name": "document", "operation": "save"}],
        artifact_id="artifact-1",
        resource_types=["documents", "images"],
    )

    assert [item.name for item in payload.resource_types] == ["documents", "images"]
    assert all(item.operation == "create" for item in payload.resource_types)
    assert payload.artifact_type == "document"


def test_generation_complete_data_defaults_to_complete_type():
    data = GenerationCompleteData(
        sid="sid-1",
        artifact_type="document",
        group_id="group-1",
        run_id="run-1",
        success=True,
        message="done",
    )

    assert data.type == "complete"


def test_store_active_run_uses_injected_id_factory_and_setter():
    calls: list[tuple[str, str]] = []

    async def fake_set_active_run(chat_id: str, run_id: str) -> None:
        calls.append((chat_id, run_id))

    import asyncio

    asyncio.run(
        store_active_run(
            "chat-1",
            object(),
            run_id_factory=lambda: "run-fixed",
            set_active_run_fn=fake_set_active_run,
        )
    )

    assert calls == [("chat-1", "run-fixed")]
    assert len(generate_active_run_id()) == 36
