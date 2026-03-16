"""Tests for field event declarations."""

from app.events.types import build_default_lifecycle_event_types
from app.events.field import (
    FIELD_EVENT_CONFIGS,
    _field_draft_entity_ids,
    _field_result_entity_ids,
    get_field_event_config,
)


def test_get_field_event_config_maps_domain_event_and_entity_scope() -> None:
    config = get_field_event_config("get")

    assert config is not None
    assert config.domain_event_names == ("artifacts.field.viewed",)
    assert config.scope == "entity"
    assert config.entity_key == "field_id"
    assert config.include_call_lifecycle is True


def test_drafts_field_event_config_is_collection_scoped() -> None:
    config = FIELD_EVENT_CONFIGS["drafts"]

    assert config.domain_event_names == ("artifacts.field.drafts.viewed",)
    assert config.scope == "collection"
    assert config.entity_key is None
    assert config.include_call_lifecycle is False


def test_field_event_types_include_domain_and_lifecycle_events() -> None:
    event_types = tuple(
        dict.fromkeys(
            event_type
            for operation in FIELD_EVENT_CONFIGS.values()
            for event_type in (
                *operation.domain_event_names,
                *(
                    build_default_lifecycle_event_types("field", operation.operation)
                    if operation.include_call_lifecycle
                    else ()
                ),
            )
        )
    )

    assert "artifacts.field.created" in event_types
    assert "artifacts.field.updated" in event_types
    assert "artifacts.field.drafts.viewed" in event_types
    for event_type in build_default_lifecycle_event_types("field", "get"):
        assert event_type in event_types


def test_create_event_config_resolves_bulk_field_ids_from_output() -> None:
    ids = _field_result_entity_ids(
        {},
        {
            "results": [
                {"field_id": "965bd24f-dfae-4063-b370-e1373df46322"},
                {"field_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
            ]
        },
    )

    assert [str(field_id) for field_id in ids] == [
        "965bd24f-dfae-4063-b370-e1373df46322",
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
    ]


def test_draft_event_config_resolves_output_or_input_draft_id() -> None:
    ids = _field_draft_entity_ids(
        {"input_draft_id": "965bd24f-dfae-4063-b370-e1373df46322"},
        {"draft_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
    )

    assert [str(draft_id) for draft_id in ids] == [
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
        "965bd24f-dfae-4063-b370-e1373df46322",
    ]
