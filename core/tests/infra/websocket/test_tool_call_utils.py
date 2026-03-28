"""Tests for websocket tool call utility helpers."""

from app.infra.websocket.tool_call_utils import (
    build_tool_output_schemas,
    extract_template_var,
    parse_partial_json,
    resolve_output_fields,
)


class TestExtractTemplateVar:
    def test_extracts_simple_variable_name(self):
        assert extract_template_var("{{ content }}") == "content"

    def test_extracts_leading_variable_from_complex_template(self):
        assert extract_template_var("{{ person.name|trim }}") == "person"

    def test_returns_none_when_no_variable_present(self):
        assert extract_template_var("plain text") is None


class TestResolveOutputFields:
    def test_maps_schema_columns_from_parsed_args(self):
        assert resolve_output_fields(
            {"content": "Hello", "title": "Greeting"},
            "write_message",
            {"write_message": {"body": "content", "heading": "title"}},
        ) == {"body": "Hello", "heading": "Greeting"}

    def test_returns_none_for_missing_tool_or_args(self):
        assert (
            resolve_output_fields(None, "tool", {"tool": {"body": "content"}}) is None
        )
        assert resolve_output_fields({}, "tool", {"tool": {"body": "content"}}) is None
        assert (
            resolve_output_fields({"content": "x"}, None, {"tool": {"body": "content"}})
            is None
        )


class TestParsePartialJson:
    def test_parses_complete_json(self):
        assert parse_partial_json('{"name":"Alice"}') == {"name": "Alice"}

    def test_closes_partial_json_objects_and_strings(self):
        assert parse_partial_json('{"name":"Ali') == {"name": "Ali"}

    def test_closes_nested_array_and_object(self):
        assert parse_partial_json('{"items":[{"name":"A"}') == {
            "items": [{"name": "A"}]
        }

    def test_returns_none_for_invalid_or_empty_json(self):
        assert parse_partial_json("") is None
        assert parse_partial_json("   ") is None
        assert parse_partial_json("[1,2,3]") is None


class TestBuildToolOutputSchemas:
    def test_builds_schema_map_from_tool_definitions(self):
        result = build_tool_output_schemas(
            [
                {
                    "name": "write_message",
                    "_args_outputs": [
                        {"name": "body", "template": "{{ content }}"},
                        {"name": "heading", "template": "{{ title|trim }}"},
                    ],
                }
            ]
        )

        assert result == {"write_message": {"body": "content", "heading": "title"}}

    def test_skips_invalid_tool_shapes(self):
        assert (
            build_tool_output_schemas(
                [
                    "not-a-dict",
                    {"name": "bad", "_args_outputs": "wrong"},
                    {
                        "name": "empty",
                        "_args_outputs": [{"name": "x", "template": "plain"}],
                    },
                ]
            )
            == {}
        )
