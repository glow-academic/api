"""Tests for tool field/signature builders."""

from app.infra.tools.build_pydantic_fields import (
    build_function_signature_string,
    build_pydantic_fields,
)


def test_build_pydantic_fields_handles_required_optional_and_unknown_types():
    tool_config = {
        "arguments": {
            "name": {"type": "string", "required": True},
            "count": {"type": "integer", "required": False},
            "tags": {"type": "array", "items": {"type": "string"}, "required": False},
            "metadata": {"type": "object", "required": False},
            "mystery": {"type": "wat", "required": True},
            "broken": "not-a-dict",
        },
        "argument_descriptions": {
            "name": "Display name",
            "count": "Number of items",
            "tags": "List of tags",
        },
        "argument_defaults": {
            "count": 3,
            "tags": ["a", "b"],
        },
    }

    fields = build_pydantic_fields(tool_config)

    assert set(fields) == {"name", "count", "tags", "metadata", "mystery"}
    assert fields["count"].default == 3
    assert fields["tags"].default == ["a", "b"]
    assert fields["metadata"].default is None
    assert fields["name"].description == "Display name"


def test_build_function_signature_string_builds_expected_annotations():
    tool_config = {
        "arguments": {
            "name": {"type": "string", "required": True},
            "enabled": {"type": "boolean", "required": False},
            "scores": {"type": "array", "items": {"type": "number"}, "required": False},
        },
        "argument_descriptions": {
            "name": "Display name",
            "enabled": "Whether enabled",
            "scores": "Score values",
        },
        "argument_defaults": {
            "enabled": True,
        },
    }

    signature, param_names = build_function_signature_string(tool_config)

    assert param_names == ["name", "enabled", "scores"]
    assert "name: str = Field(..., description='Display name')" in signature
    assert (
        "enabled: bool | None = Field(default=True, description='Whether enabled')"
        in signature
    )
    assert (
        "scores: list[float] | None = Field(default=None, description='Score values')"
        in signature
    )
