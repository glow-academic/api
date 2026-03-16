"""Tests for Jinja template rendering helpers."""

import pytest
from jinja2 import TemplateError

from app.utils.settings.theme import ThemeTokens
from app.utils.templates.jinja_renderer import (
    inject_theme_css_variables,
    render_template,
)


def _theme() -> ThemeTokens:
    return ThemeTokens(
        background="oklch(1 0 0)",
        foreground="oklch(0 0 0)",
        card="oklch(1 0 0)",
        cardForeground="oklch(0 0 0)",
        popover="oklch(1 0 0)",
        popoverForeground="oklch(0 0 0)",
        primary="oklch(0.5 0.1 200)",
        primaryForeground="oklch(1 0 0)",
        secondary="oklch(0.9 0 0)",
        secondaryForeground="oklch(0 0 0)",
        muted="oklch(0.95 0 0)",
        mutedForeground="oklch(0.3 0 0)",
        accent="oklch(0.8 0.05 180)",
        accentForeground="oklch(0 0 0)",
        destructive="oklch(0.6 0.2 20)",
        border="oklch(0.8 0 0)",
        input="oklch(0.8 0 0)",
        ring="oklch(0.5 0.1 200)",
        success="oklch(0.6 0.1 140)",
        successForeground="oklch(1 0 0)",
        warning="oklch(0.8 0.12 80)",
        warningForeground="oklch(0 0 0)",
        info="oklch(0.6 0.08 220)",
        infoForeground="oklch(1 0 0)",
        chart1="oklch(0.6 0.1 10)",
        chart2="oklch(0.6 0.1 20)",
        chart3="oklch(0.6 0.1 30)",
        chart4="oklch(0.6 0.1 40)",
        chart5="oklch(0.6 0.1 50)",
        sidebar="oklch(0.95 0 0)",
        sidebarForeground="oklch(0 0 0)",
        sidebarPrimary="oklch(0.5 0.1 200)",
        sidebarPrimaryForeground="oklch(1 0 0)",
        sidebarAccent="oklch(0.9 0.02 180)",
        sidebarAccentForeground="oklch(0 0 0)",
        sidebarBorder="oklch(0.85 0 0)",
        sidebarRing="oklch(0.5 0.1 200)",
    )


def test_inject_theme_css_variables_inserts_style_into_head():
    html = "<html><head></head><body>hello</body></html>"

    result = inject_theme_css_variables(html, _theme())

    assert "<style>" in result
    assert "--primary: oklch(0.5 0.1 200);" in result


def test_render_template_renders_context_and_escapes_html():
    result = render_template(
        "<html><body>Hello {{ name }}</body></html>",
        {"name": "<b>Alice</b>"},
        _theme(),
    )

    assert "Hello &lt;b&gt;Alice&lt;/b&gt;" in result


def test_render_template_raises_for_invalid_template():
    with pytest.raises(TemplateError):
        render_template("{{ bad", {}, _theme())
