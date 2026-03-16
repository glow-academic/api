"""Tests for pure template validation helper."""

import pytest

from app.infra.tools.render_tool_template import (
    get_rendered_template_values,
    validate_jinja_template,
)


def test_validate_jinja_template_accepts_empty_and_valid_templates():
    assert validate_jinja_template("") == (True, None)
    assert validate_jinja_template("Hello {{ name }}") == (True, None)


def test_validate_jinja_template_rejects_invalid_syntax():
    valid, error = validate_jinja_template("Hello {{ name ")

    assert valid is False
    assert error is not None
    assert "Template syntax error" in error


@pytest.mark.asyncio
async def test_get_rendered_template_values_is_explicit_stub():
    assert await get_rendered_template_values(None, None) is None
