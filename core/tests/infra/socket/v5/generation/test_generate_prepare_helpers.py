"""Tests for extracted pure helpers in generate_prepare_impl."""

from uuid import UUID, uuid4

import pytest

from app.infra.websocket.generate_prepare_impl import (
    build_generate_artifact_payload,
    build_generation_started_payload,
    build_generation_work_units,
    enrich_generation_metadata,
    parse_generation_identity,
    resolve_primary_artifact_type,
)
from app.infra.websocket.prepare_types import LLMConfig


def test_resolve_primary_artifact_type_uses_first_entry_name():
    assert (
        resolve_primary_artifact_type(
            {"artifact_types": [{"name": "agent", "operation": "get"}]}
        )
        == "agent"
    )


def test_resolve_primary_artifact_type_falls_back_to_unknown():
    assert resolve_primary_artifact_type({"artifact_types": []}) == "unknown"
    assert resolve_primary_artifact_type({}) == "unknown"


def test_parse_generation_identity_returns_uuid_tuple():
    parsed = parse_generation_identity(
        {
            "profile_id": "00000000-0000-0000-0000-000000000001",
            "profiles_id": "00000000-0000-0000-0000-000000000002",
            "session_id": "00000000-0000-0000-0000-000000000003",
            "group_id": "00000000-0000-0000-0000-000000000004",
        }
    )

    assert parsed == (
        UUID("00000000-0000-0000-0000-000000000001"),
        UUID("00000000-0000-0000-0000-000000000002"),
        UUID("00000000-0000-0000-0000-000000000003"),
        UUID("00000000-0000-0000-0000-000000000004"),
    )


def test_parse_generation_identity_raises_on_invalid_uuid():
    with pytest.raises(ValueError):
        parse_generation_identity(
            {
                "profile_id": "bad",
                "profiles_id": "00000000-0000-0000-0000-000000000002",
                "session_id": "00000000-0000-0000-0000-000000000003",
                "group_id": "00000000-0000-0000-0000-000000000004",
            }
        )


def test_build_generation_work_units_marks_resource_and_entry_targets():
    agent_id = uuid4()

    units = build_generation_work_units(
        {
            agent_id: ["names", "summary"],
        },
        {"names"},
    )

    assert [(u.agent_id, u.target_type, u.target_name) for u in units] == [
        (str(agent_id), "resource", "names"),
        (str(agent_id), "entry", "summary"),
    ]


def test_enrich_generation_metadata_adds_test_fields_when_available():
    agent_id = uuid4()
    invocation_id = uuid4()

    enriched = enrich_generation_metadata(
        {"existing": "value"},
        generation_test_id="test-1",
        generation_invocation_map={agent_id: invocation_id},
        agent_group_id=agent_id,
    )

    assert enriched == {
        "existing": "value",
        "generation_test_id": "test-1",
        "test_invocation_id": str(invocation_id),
    }


def test_enrich_generation_metadata_leaves_payload_unchanged_without_match():
    enriched = enrich_generation_metadata(
        {"existing": "value"},
        generation_test_id=None,
        generation_invocation_map=None,
        agent_group_id=uuid4(),
    )

    assert enriched == {"existing": "value"}


def test_build_generation_started_payload_serializes_expected_shape():
    payload = build_generation_started_payload(
        sid="sid-1",
        artifact_type="agent",
        group_id="group-1",
        run_id="run-1",
        resource_types=["names", "descriptions"],
    )

    assert payload == {
        "sid": "sid-1",
        "artifact_type": "agent",
        "group_id": "group-1",
        "run_id": "run-1",
        "resource_types": ["names", "descriptions"],
    }


def test_build_generate_artifact_payload_serializes_dispatch_contract():
    agent_id = uuid4()
    artifact_id = uuid4()
    draft_id = uuid4()
    llm_config = LLMConfig(
        model="gpt-4o",
        api_key="sk-test",
        base_url="https://api.openai.com",
        temperature=0.7,
        reasoning="medium",
        provider="openai",
        voice=None,
        quality="high",
    )

    payload = build_generate_artifact_payload(
        sid="sid-1",
        artifact_type="agent",
        agent_resource_types=["names"],
        run_id="run-1",
        group_id="group-1",
        modality="call",
        all_messages=[{"role": "user", "content": "hello"}],
        llm_config=llm_config,
        scoped_tools=[{"type": "function", "name": "search_docs"}],
        metadata={"generation_test_id": "test-1"},
        profile_id="profile-1",
        profiles_id="profiles-1",
        session_id="session-1",
        artifact_id=artifact_id,
        draft_id=draft_id,
        developer_instruction_templates=["Do the thing"],
        agent_id=agent_id,
    )

    assert payload == {
        "sid": "sid-1",
        "run_id": "run-1",
        "group_id": "group-1",
        "modality": "call",
        "artifact_type": "agent",
        "resource_type": "names",
        "resource_types": None,
        "resource_id": None,
        "messages": [{"role": "user", "content": "hello"}],
        "llm_config": {
            "model": "gpt-4o",
            "api_key": "sk-test",
            "base_url": "https://api.openai.com",
            "temperature": 0.7,
            "reasoning": "medium",
            "provider": "openai",
            "voice": None,
            "quality": "high",
            "length_seconds": None,
            "response_format": None,
            "tool_choice": "required",
            "extra_body": None,
        },
        "tools": [{"type": "function", "name": "search_docs"}],
        "tool_timeout_seconds": 60.0,
        "file_path": None,
        "mime_type": None,
        "file_size": None,
        "upload_id": None,
        "chat_id": None,
        "metadata": {"generation_test_id": "test-1"},
        "message_id": None,
        "profile_id": "profile-1",
        "profiles_id": "profiles-1",
        "session_id": "session-1",
        "artifact_id": str(artifact_id),
        "draft_id": str(draft_id),
        "developer_instruction_templates": ["Do the thing"],
        "agent_id": str(agent_id),
    }
