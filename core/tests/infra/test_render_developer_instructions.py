"""Tests for rendering developer instructions and tool serialization."""

from types import SimpleNamespace

from pydantic import BaseModel

from app.infra.generation.render_developer_instructions import (
    convert_tools_to_dict,
    render_developer_instructions,
)


class DemoToolModel(BaseModel):
    id: str
    name: str
    description: str
    active: bool = True


class FakeNamedTuple:
    def _asdict(self):
        return {"id": "tool-1", "name": "named", "description": "desc", "active": True}


class DictLikeTool:
    def dict(self):
        return {
            "id": "tool-2",
            "name": "dict-tool",
            "description": "desc",
            "active": True,
        }


class TestRenderDeveloperInstructions:
    def test_renders_templates_from_dict_context(self):
        rendered = render_developer_instructions(
            ["Hello {{ user }}", "{% for item in items %}{{ item }} {% endfor %}"],
            {"user": "Alice", "items": ["one", "two"]},
        )

        assert rendered == ["Hello Alice", "one two"]

    def test_renders_templates_from_json_context(self):
        rendered = render_developer_instructions(
            ["Hello {{ user }}"],
            '{"user": "Bob"}',
        )

        assert rendered == ["Hello Bob"]

    def test_skips_blank_templates_and_failed_renders(self):
        rendered = render_developer_instructions(
            ["", "   ", "{% if %}", "Hello {{ name }}"],
            {"name": "Charlie"},
        )

        assert rendered == ["Hello Charlie"]

    def test_invalid_context_uses_empty_dict(self):
        rendered = render_developer_instructions(
            ["{{ missing or 'fallback' }}"],
            object(),
        )

        assert rendered == ["fallback"]

    def test_empty_templates_return_empty_list(self):
        assert render_developer_instructions([], {"name": "x"}) == []
        assert render_developer_instructions(None, {"name": "x"}) == []


class TestConvertToolsToDict:
    def test_handles_multiple_tool_shapes(self):
        result = convert_tools_to_dict(
            [
                FakeNamedTuple(),
                DemoToolModel(id="tool-3", name="pydantic", description="desc"),
                DictLikeTool(),
                {"id": "tool-4", "name": "dict", "description": "desc", "active": True},
                (
                    "tool-5",
                    "tuple-tool",
                    "desc",
                    "resource",
                    "artifact",
                    {"arg": "string"},
                    {"arg": "desc"},
                    {"arg": "default"},
                    True,
                ),
            ]
        )

        assert [tool["name"] for tool in result] == [
            "named",
            "pydantic",
            "dict-tool",
            "dict",
            "tuple-tool",
        ]

    def test_filters_inactive_or_invalid_tools(self):
        result = convert_tools_to_dict(
            [
                None,
                {
                    "id": "tool-6",
                    "name": "inactive",
                    "description": "desc",
                    "active": False,
                },
                SimpleNamespace(name="unsupported"),
            ]
        )

        assert result is None

    def test_returns_none_for_empty_input(self):
        assert convert_tools_to_dict([]) is None
        assert convert_tools_to_dict(None) is None
