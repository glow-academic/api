"""Tests for the low-level theme color utilities.

Covers ``app.utils.theme.color_utils`` (oklch parse/format + tint/shade/
contrast) and ``app.utils.theme.oklch_to_hex`` (oklch↔hex round-trips).

The higher-level token derivation (``app.utils.settings.theme``) is
tested separately in ``tests/utils/settings/test_theme.py``; this file
owns the primitive color math those derivations are built on.
"""

import math

import pytest

from app.utils.theme.color_utils import (
    ensure_contrast,
    format_oklch,
    parse_oklch,
    shade,
    tint,
)
from app.utils.theme.oklch_to_hex import hex_to_oklch, oklch_to_hex
from app.utils.theme.oklch_to_hex import parse_oklch as parse_triplet


# ── color_utils.parse_oklch / format_oklch ──


def test_parse_oklch_with_alpha_percentage():
    assert parse_oklch("oklch(0.7 0.2 120 / 50%)") == (0.7, 0.2, 120.0, 0.5)


def test_parse_oklch_without_alpha_returns_none_alpha():
    assert parse_oklch("oklch(0.4 0.1 200)") == (0.4, 0.1, 200.0, None)


def test_parse_oklch_with_raw_alpha_is_not_divided():
    assert parse_oklch("oklch(0.4 0.1 200 / 0.3)") == (0.4, 0.1, 200.0, 0.3)


def test_parse_oklch_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid oklch format"):
        parse_oklch("rgb(255, 0, 0)")


def test_format_oklch_round_trips_through_parse():
    formatted = format_oklch(0.5, 0.12, 240.0)
    assert formatted == "oklch(0.5 0.12 240.0)"
    assert parse_oklch(formatted) == (0.5, 0.12, 240.0, None)

    with_alpha = format_oklch(0.5, 0.12, 240.0, 0.4)
    assert with_alpha == "oklch(0.5 0.12 240.0 / 0.4)"


# ── color_utils.tint / shade ──


def test_tint_and_shade_adjust_lightness_in_expected_direction():
    tinted = tint("oklch(0.4 0.2 100)", 0.5)
    shaded = shade("oklch(0.4 0.2 100)", 0.5)

    assert parse_oklch(tinted)[0] > 0.4
    assert parse_oklch(shaded)[0] < 0.4


def test_tint_lightens_toward_white_and_desaturates():
    l, c, h, _ = parse_oklch(tint("oklch(0.4 0.2 100)", 0.5))
    # new_l = 0.4 + (1 - 0.4) * 0.5 = 0.7 ; new_c = 0.2 * (1 - 0.25) = 0.15
    assert l == pytest.approx(0.7)
    assert c == pytest.approx(0.15)
    assert h == 100.0


def test_shade_darkens_toward_black_and_enriches_chroma():
    l, c, _, _ = parse_oklch(shade("oklch(0.4 0.2 100)", 0.5))
    # new_l = 0.4 * 0.5 = 0.2 ; new_c = 0.2 * (1 + 0.05) = 0.21
    assert l == pytest.approx(0.2)
    assert c == pytest.approx(0.21)


def test_tint_and_shade_preserve_alpha():
    assert parse_oklch(tint("oklch(0.4 0.2 100 / 50%)", 0.5))[3] == pytest.approx(0.5)
    assert parse_oklch(shade("oklch(0.4 0.2 100 / 50%)", 0.5))[3] == pytest.approx(0.5)


# ── color_utils.ensure_contrast ──


def test_ensure_contrast_forces_dark_text_on_light_background():
    result = ensure_contrast("oklch(0.95 0 0)", "oklch(0.9 0.1 200)")
    assert parse_oklch(result)[:3] == (0.145, 0.0, 0.0)


def test_ensure_contrast_forces_light_text_on_dark_background():
    result = ensure_contrast("oklch(0.1 0 0)", "oklch(0.2 0.1 200)")
    assert parse_oklch(result)[:3] == (0.985, 0.0, 0.0)


def test_ensure_contrast_leaves_already_contrasting_candidate_untouched():
    # Light bg, already-dark candidate (L <= 0.3) stays as-is.
    result = ensure_contrast("oklch(0.95 0 0)", "oklch(0.2 0.05 30)")
    assert parse_oklch(result)[:3] == (0.2, 0.05, 30.0)


# ── oklch_to_hex ──


def test_oklch_to_hex_parse_triplet_drops_alpha():
    assert parse_triplet("oklch(0.627 0.258 29.0)") == (0.627, 0.258, 29.0)
    # parse_triplet ignores the alpha component entirely.
    assert parse_triplet("oklch(0.627 0.258 29.0 / 50%)") == (0.627, 0.258, 29.0)


def test_oklch_to_hex_returns_7_char_hex():
    hex_value = oklch_to_hex("oklch(0.627 0.258 29.0)")
    assert hex_value.startswith("#")
    assert len(hex_value) == 7
    assert all(ch in "0123456789abcdef" for ch in hex_value[1:])


def test_pure_white_and_black_round_trip_to_expected_hex():
    # L=1 C=0 → white; L=0 C=0 → black.
    assert oklch_to_hex("oklch(1.0 0.0 0.0)") == "#ffffff"
    assert oklch_to_hex("oklch(0.0 0.0 0.0)") == "#000000"


def test_hex_to_oklch_emits_parseable_oklch_string():
    back = hex_to_oklch("#ff0000")
    assert back.startswith("oklch(")
    l, c, h = parse_triplet(back)
    # Pure red sits near L~0.63, chroma high, hue ~29° in OKLCH.
    assert l == pytest.approx(0.628, abs=0.01)
    assert c > 0.2
    assert h == pytest.approx(29.0, abs=1.0)


def test_hex_oklch_hex_round_trip_is_stable():
    for hex_in in ("#3b82f6", "#10b981", "#dc2626"):
        round_tripped = oklch_to_hex(hex_to_oklch(hex_in))
        r0, g0, b0 = (int(hex_in[i : i + 2], 16) for i in (1, 3, 5))
        r1, g1, b1 = (int(round_tripped[i : i + 2], 16) for i in (1, 3, 5))
        # Allow small rounding drift across the float pipeline.
        assert math.isclose(r0, r1, abs_tol=2)
        assert math.isclose(g0, g1, abs_tol=2)
        assert math.isclose(b0, b1, abs_tol=2)


def test_oklch_to_hex_parse_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid oklch format"):
        parse_triplet("rgb(255, 0, 0)")
