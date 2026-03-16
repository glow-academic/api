"""Tests for tool format conversion helpers."""

from types import SimpleNamespace

from app.infra.artifacts.convert_tools_to_openai_format import (
    convert_tools_to_openai_format,
    convert_tools_to_responses_format,
)


class TestConvertToolsToOpenaiFormat:
    def test_converts_active_tools_with_argument_schema(self):
        tools = [
            {
                "name": "search_docs",
                "description": "Search documents",
                "active": True,
                "arguments": {
                    "query": {"type": "string", "required": True},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "filters": {"type": "object"},
                    "count": {"type": "integer"},
                    "mystery": {"type": "unsupported"},
                },
                "argument_descriptions": {
                    "query": "Search text",
                    "tags": "Tags",
                    "filters": "Structured filters",
                    "count": "Result count",
                    "mystery": "Falls back to string",
                },
            }
        ]

        result = convert_tools_to_openai_format(tools)

        assert result == [
            {
                "type": "function",
                "function": {
                    "name": "search_docs",
                    "description": "Search documents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search text",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags",
                            },
                            "filters": {
                                "type": "object",
                                "description": "Structured filters",
                            },
                            "count": {
                                "type": "integer",
                                "description": "Result count",
                            },
                            "mystery": {
                                "type": "string",
                                "description": "Falls back to string",
                            },
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

    def test_skips_inactive_or_unnamed_tools(self):
        result = convert_tools_to_openai_format(
            [
                {"name": "", "active": True},
                {"name": "inactive", "active": False},
                SimpleNamespace(
                    name="object-tool",
                    active=True,
                    arguments={},
                    argument_descriptions={},
                ),
            ]
        )

        assert result == [
            {
                "type": "function",
                "function": {
                    "name": "object-tool",
                    "description": "",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }
        ]


class TestConvertToolsToResponsesFormat:
    def test_converts_tools_to_responses_api_shape(self):
        result = convert_tools_to_responses_format(
            [
                {
                    "name": "search_docs",
                    "description": "Search documents",
                    "active": True,
                    "arguments": {
                        "query": {"type": "string"},
                        "count": {"type": "integer"},
                    },
                    "argument_descriptions": {
                        "query": "Search text",
                        "count": "Result count",
                    },
                }
            ]
        )

        assert result == [
            {
                "type": "function",
                "name": "search_docs",
                "description": "Search documents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search text",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Result count",
                        },
                    },
                    "required": ["query", "count"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        ]
