"""Tests for app.utils.theme.color_utils."""

import pytest

from app.utils.theme.color_utils import (
    ensure_contrast,
    format_oklch,
    parse_oklch,
    shade,
    tint,
)


# --- parse_oklch ---

def test_parse_oklch_basic():
    """Parses a basic oklch(L C H) string."""
    l, c, h, alpha = parse_oklch("oklch(0.5 0.2 120)")
    assert l == pytest.approx(0.5)
    assert c == pytest.approx(0.2)
    assert h == pytest.approx(120.0)
    assert alpha is None


def test_parse_oklch_with_alpha():
    """Parses oklch with alpha channel."""
    l, c, h, alpha = parse_oklch("oklch(0.7 0.1 240 / 0.8)")
    assert l == pytest.approx(0.7)
    assert alpha == pytest.approx(0.8)


def test_parse_oklch_with_percentage_alpha():
    """Alpha given as percentage is converted to 0-1 range."""
    _, _, _, alpha = parse_oklch("oklch(0.5 0.2 120 / 50%)")
    assert alpha == pytest.approx(0.5)


def test_parse_oklch_invalid_format_raises():
    """Invalid oklch string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid oklch"):
        parse_oklch("rgb(255, 0, 0)")


# --- format_oklch ---

def test_format_oklch_without_alpha():
    """Formats L C H without alpha."""
    assert format_oklch(0.5, 0.2, 120) == "oklch(0.5 0.2 120)"


def test_format_oklch_with_alpha():
    """Formats L C H with alpha."""
    assert format_oklch(0.5, 0.2, 120, 0.8) == "oklch(0.5 0.2 120 / 0.8)"


# --- tint ---

def test_tint_zero_amount_no_change():
    """Tint with amount=0 returns the same color."""
    color = "oklch(0.5 0.2 120)"
    result = tint(color, 0.0)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(0.5)
    assert h == pytest.approx(120.0)


def test_tint_full_amount_approaches_white():
    """Tint with amount=1 moves lightness towards 1.0."""
    result = tint("oklch(0.5 0.2 120)", 1.0)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(1.0)
    # Chroma should be halved at amount=1.0 (c * (1.0 - 1.0*0.5) = c * 0.5)
    assert c == pytest.approx(0.1)


# --- shade ---

def test_shade_zero_amount_no_change():
    """Shade with amount=0 returns the same color."""
    color = "oklch(0.5 0.2 120)"
    result = shade(color, 0.0)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(0.5)


def test_shade_full_amount_approaches_black():
    """Shade with amount=1 moves lightness to 0."""
    result = shade("oklch(0.5 0.2 120)", 1.0)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(0.0)


# --- ensure_contrast ---

def test_ensure_contrast_light_bg_dark_text():
    """Light background forces dark text."""
    bg = "oklch(0.9 0.1 120)"
    candidate = "oklch(0.8 0.1 120)"  # too light for light bg
    result = ensure_contrast(bg, candidate)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(0.145)  # dark text


def test_ensure_contrast_dark_bg_light_text():
    """Dark background forces light text."""
    bg = "oklch(0.2 0.1 120)"
    candidate = "oklch(0.3 0.1 120)"  # too dark for dark bg
    result = ensure_contrast(bg, candidate)
    l, c, h, _ = parse_oklch(result)
    assert l == pytest.approx(0.985)  # light text
