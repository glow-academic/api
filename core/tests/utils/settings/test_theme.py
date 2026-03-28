"""Tests for theme/color utility helpers."""

import pytest

from app.utils.settings.theme import ThemePrimitives, derive_theme_tokens
from app.utils.theme.color_utils import ensure_contrast, parse_oklch, shade, tint
from app.utils.theme.oklch_to_hex import (
    hex_to_oklch,
    oklch_to_hex,
)
from app.utils.theme.oklch_to_hex import (
    parse_oklch as parse_triplet,
)


def test_parse_oklch_with_alpha_percentage():
    assert parse_oklch("oklch(0.7 0.2 120 / 50%)") == (0.7, 0.2, 120.0, 0.5)


def test_tint_and_shade_adjust_lightness_in_expected_direction():
    tinted = tint("oklch(0.4 0.2 100)", 0.5)
    shaded = shade("oklch(0.4 0.2 100)", 0.5)

    assert parse_oklch(tinted)[0] > 0.4
    assert parse_oklch(shaded)[0] < 0.4


def test_ensure_contrast_forces_dark_text_on_light_background():
    result = ensure_contrast("oklch(0.95 0 0)", "oklch(0.9 0.1 200)")

    assert parse_oklch(result)[:3] == (0.145, 0.0, 0.0)


def test_oklch_parse_and_round_trip_return_expected_shapes():
    parsed = parse_triplet("oklch(0.627 0.258 29.0)")
    hex_value = oklch_to_hex("oklch(0.627 0.258 29.0)")
    back = hex_to_oklch("#ff0000")

    assert parsed == (0.627, 0.258, 29.0)
    assert hex_value.startswith("#")
    assert len(hex_value) == 7
    assert back.startswith("oklch(")


def test_oklch_parse_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid oklch format"):
        parse_triplet("rgb(255, 0, 0)")


def test_derive_theme_tokens_normalizes_hex_and_generates_contrasting_tokens():
    tokens = derive_theme_tokens(
        ThemePrimitives(
            primary="#ff0000",
            accent="oklch(0.7 0.1 200)",
            background="#ffffff",
            surface="#ffffff",
            success="#00ff00",
            warning="#ffff00",
            error="#ff0000",
            sidebarBackground="#ffffff",
            sidebarPrimary="#000000",
            chart1="#ff0000",
            chart2="#00ff00",
            chart3="#0000ff",
            chart4="#ffffff",
            chart5="#000000",
        )
    )

    assert tokens.primary.startswith("oklch(")
    assert tokens.background.startswith("oklch(")
    assert tokens.primaryForeground.startswith("oklch(")
    assert tokens.sidebarPrimaryForeground.startswith("oklch(")
