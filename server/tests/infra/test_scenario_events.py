"""Tests for scenario event declarations."""

from app.events.types import build_default_lifecycle_event_types
from app.events.scenario import (
    SCENARIO_EVENT_CONFIGS,
    _scenario_draft_entity_ids,
    _scenario_result_entity_ids,
    get_scenario_event_config,
)


def test_get_scenario_event_config_maps_domain_event_and_entity_scope() -> None:
    config = get_scenario_event_config("get")

    assert config is not None
    assert config.domain_event_names == ("artifacts.scenario.viewed",)
    assert config.scope == "entity"
    assert config.entity_key == "scenario_id"
    assert config.include_call_lifecycle is True


def test_drafts_scenario_event_config_is_collection_scoped() -> None:
    config = SCENARIO_EVENT_CONFIGS["drafts"]

    assert config.domain_event_names == ("artifacts.scenario.drafts.viewed",)
    assert config.scope == "collection"
    assert config.entity_key is None
    assert config.include_call_lifecycle is False


def test_scenario_event_types_include_domain_and_lifecycle_events() -> None:
    event_types = tuple(
        dict.fromkeys(
            event_type
            for operation in SCENARIO_EVENT_CONFIGS.values()
            for event_type in (
                *operation.domain_event_names,
                *(
                    build_default_lifecycle_event_types("scenario", operation.operation)
                    if operation.include_call_lifecycle
                    else ()
                ),
            )
        )
    )

    assert "artifacts.scenario.created" in event_types
    assert "artifacts.scenario.updated" in event_types
    assert "artifacts.scenario.drafts.viewed" in event_types
    for event_type in build_default_lifecycle_event_types("scenario", "get"):
        assert event_type in event_types


def test_create_event_config_resolves_bulk_scenario_ids_from_output() -> None:
    ids = _scenario_result_entity_ids(
        {},
        {
            "results": [
                {"scenario_id": "965bd24f-dfae-4063-b370-e1373df46322"},
                {"scenario_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
            ]
        },
    )

    assert [str(scenario_id) for scenario_id in ids] == [
        "965bd24f-dfae-4063-b370-e1373df46322",
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
    ]


def test_draft_event_config_resolves_output_or_input_draft_id() -> None:
    ids = _scenario_draft_entity_ids(
        {"input_draft_id": "965bd24f-dfae-4063-b370-e1373df46322"},
        {"draft_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
    )

    assert [str(draft_id) for draft_id in ids] == [
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
        "965bd24f-dfae-4063-b370-e1373df46322",
    ]
