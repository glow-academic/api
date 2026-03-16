"""Tests for cohort event declarations."""

from app.events.types import build_default_lifecycle_event_types
from app.events.cohort import (
    COHORT_EVENT_CONFIGS,
    _cohort_draft_entity_ids,
    _cohort_result_entity_ids,
    get_cohort_event_config,
)


def test_get_cohort_event_config_maps_domain_event_and_entity_scope() -> None:
    config = get_cohort_event_config("get")

    assert config is not None
    assert config.domain_event_names == ("artifacts.cohort.viewed",)
    assert config.scope == "entity"
    assert config.entity_key == "cohort_id"
    assert config.include_call_lifecycle is True


def test_drafts_cohort_event_config_is_collection_scoped() -> None:
    config = COHORT_EVENT_CONFIGS["drafts"]

    assert config.domain_event_names == ("artifacts.cohort.drafts.viewed",)
    assert config.scope == "collection"
    assert config.entity_key is None
    assert config.include_call_lifecycle is False


def test_cohort_event_types_include_domain_and_lifecycle_events() -> None:
    event_types = tuple(
        dict.fromkeys(
            event_type
            for operation in COHORT_EVENT_CONFIGS.values()
            for event_type in (
                *operation.domain_event_names,
                *(
                    build_default_lifecycle_event_types("cohort", operation.operation)
                    if operation.include_call_lifecycle
                    else ()
                ),
            )
        )
    )

    assert "artifacts.cohort.created" in event_types
    assert "artifacts.cohort.updated" in event_types
    assert "artifacts.cohort.drafts.viewed" in event_types
    for event_type in build_default_lifecycle_event_types("cohort", "get"):
        assert event_type in event_types


def test_create_event_config_resolves_bulk_cohort_ids_from_output() -> None:
    ids = _cohort_result_entity_ids(
        {},
        {
            "results": [
                {"cohort_id": "965bd24f-dfae-4063-b370-e1373df46322"},
                {"cohort_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
            ]
        },
    )

    assert [str(cohort_id) for cohort_id in ids] == [
        "965bd24f-dfae-4063-b370-e1373df46322",
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
    ]


def test_draft_event_config_resolves_output_or_input_draft_id() -> None:
    ids = _cohort_draft_entity_ids(
        {"input_draft_id": "965bd24f-dfae-4063-b370-e1373df46322"},
        {"draft_id": "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752"},
    )

    assert [str(draft_id) for draft_id in ids] == [
        "0c6a4d42-bc9a-4fb3-a00c-4ad1a1726752",
        "965bd24f-dfae-4063-b370-e1373df46322",
    ]
