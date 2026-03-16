"""Tests for pure helpers in generate_artifact_impl."""

from uuid import uuid4

from app.infra.websocket.generate_artifact_impl import (
    _build_refetch_kwargs,
    _event_name_for_modality,
    _parse_bool,
    _parse_int,
    _validate_responses_tools,
)


def test_parse_bool_handles_supported_inputs():
    assert _parse_bool(True) is True
    assert _parse_bool(False) is False
    assert _parse_bool("true") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True
    assert _parse_bool("false") is False
    assert _parse_bool(None) is None


def test_parse_int_handles_strings_and_invalid_values():
    assert _parse_int(5) == 5
    assert _parse_int("7") == 7
    assert _parse_int("abc") is None
    assert _parse_int(None) is None


def test_build_refetch_kwargs_for_persona_converts_ids_and_flags():
    profile_id = uuid4()
    artifact_id = uuid4()
    draft_id = uuid4()
    parameter_id = uuid4()

    kwargs = _build_refetch_kwargs(
        "persona",
        {
            "parameter_ids": f"{parameter_id}, not-a-uuid",
            "color_search": "blue",
            "icon_show_selected": "true",
            "parameter_field_show_selected": "0",
        },
        profile_id,
        artifact_id,
        draft_id,
        "persona_id",
    )

    assert kwargs["bypass_cache"] is True
    assert kwargs["profile_id"] == profile_id
    assert kwargs["persona_id"] == artifact_id
    assert kwargs["draft_id"] == draft_id
    assert kwargs["color_search"] == "blue"
    assert kwargs["icon_show_selected"] is True
    assert kwargs["parameter_field_show_selected"] is False
    assert "parameter_ids" not in kwargs


def test_build_refetch_kwargs_for_home_converts_history_values():
    kwargs = _build_refetch_kwargs(
        "home",
        {
            "history_page": "3",
            "history_page_size": "25",
            "history_show_archived": "yes",
            "history_infinite_mode": "false",
            "history_sort_by": "created_at",
        },
        None,
        None,
        None,
        "",
    )

    assert kwargs == {
        "bypass_cache": True,
        "history_page": 3,
        "history_page_size": 25,
        "history_show_archived": True,
        "history_infinite_mode": False,
        "history_sort_by": "created_at",
    }


def test_build_refetch_kwargs_passthroughs_non_empty_values_for_other_artifacts():
    artifact_id = uuid4()

    kwargs = _build_refetch_kwargs(
        "agent",
        {
            "name_search": "helper",
            "empty_value": "",
            "none_value": None,
        },
        None,
        artifact_id,
        None,
        "agent_id",
    )

    assert kwargs == {
        "bypass_cache": True,
        "agent_id": artifact_id,
        "name_search": "helper",
    }


def test_event_name_for_modality_builds_expected_name():
    assert _event_name_for_modality("image", "start") == "generate_image_start"


def test_validate_responses_tools_normalizes_function_shapes():
    tools = _validate_responses_tools(
        [
            {
                "type": "function",
                "name": "search_docs",
                "parameters": {"type": "object"},
                "strict": True,
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_user",
                    "parameters": {"type": "object"},
                    "description": "Lookup a user",
                    "strict": False,
                },
            },
            {
                "type": "other",
                "name": "ignored",
            },
        ]
    )

    assert tools == [
        {
            "type": "function",
            "name": "search_docs",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "lookup_user",
            "parameters": {"type": "object"},
            "description": "Lookup a user",
            "strict": False,
        },
    ]
