"""Tests for persona event declarations."""

from app.events.types import OperationErrorEvent, build_default_lifecycle_event_types
from app.events.persona import (
    PERSONA_EVENT_CONFIGS,
    PERSONA_EVENT_TYPES,
    _persona_draft_entity_ids,
    _persona_result_entity_ids,
    get_persona_event_config,
)
from app.infra.persona.types import (
    CreatePersonaApiResponse,
    GetPersonaApiRequest,
    GetPersonaApiResponse,
)


def test_get_persona_event_config_maps_domain_event_and_entity_scope() -> None:
    config = get_persona_event_config("get")

    assert config is not None
    assert config.domain_event_names == ("artifacts.persona.viewed",)
    assert config.domain_events["artifacts.persona.viewed"] is None
    assert config.scope == "entity"
    assert config.entity_key == "persona_id"
    assert config.include_call_lifecycle is True
    # Lifecycle models
    assert config.lifecycle_models["started"] is GetPersonaApiRequest
    assert config.lifecycle_models["completed"] is GetPersonaApiResponse
    assert config.lifecycle_models["failed"] is OperationErrorEvent


def test_drafts_event_config_is_collection_scoped() -> None:
    config = PERSONA_EVENT_CONFIGS["drafts"]

    assert config.domain_event_names == ("artifacts.persona.drafts.viewed",)
    assert config.scope == "collection"
    assert config.entity_key is None
    assert config.include_call_lifecycle is False


def test_create_event_config_has_typed_domain_event() -> None:
    config = PERSONA_EVENT_CONFIGS["create"]

    assert config.domain_events["artifacts.persona.created"] is CreatePersonaApiResponse


def test_persona_event_types_include_domain_and_lifecycle_events() -> None:
    assert "artifacts.persona.created" in PERSONA_EVENT_TYPES
    assert "artifacts.persona.updated" in PERSONA_EVENT_TYPES
    assert "artifacts.persona.drafts.viewed" in PERSONA_EVENT_TYPES
    for event_type in build_default_lifecycle_event_types("persona", "get"):
        assert event_type in PERSONA_EVENT_TYPES


def test_create_event_config_resolves_bulk_persona_ids_from_output() -> None:
    ids = _persona_result_entity_ids(
        {},
        {
            "results": [
                {"persona_id": "965bd24f-dfae-4063-b370-e1373df46322"},
                {"persona_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
            ]
        },
    )

    assert [str(persona_id) for persona_id in ids] == [
        "965bd24f-dfae-4063-b370-e1373df46322",
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
    ]


def test_draft_event_config_resolves_output_or_input_draft_id() -> None:
    ids = _persona_draft_entity_ids(
        {"input_draft_id": "965bd24f-dfae-4063-b370-e1373df46322"},
        {"draft_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
    )

    assert [str(draft_id) for draft_id in ids] == [
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
        "965bd24f-dfae-4063-b370-e1373df46322",
    ]
