"""Tests for app.utils.theme.oklch_to_hex."""

import pytest

from app.utils.theme.oklch_to_hex import hex_to_oklch, oklch_to_hex, parse_oklch


# --- parse_oklch (the oklch_to_hex module's version) ---

def test_parse_oklch_basic():
    """Parses basic oklch string into (L, C, H) tuple."""
    l, c, h = parse_oklch("oklch(0.5 0.2 120)")
    assert l == pytest.approx(0.5)
    assert c == pytest.approx(0.2)
    assert h == pytest.approx(120.0)


def test_parse_oklch_invalid_raises():
    """Invalid string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid oklch"):
        parse_oklch("not-a-color")


# --- oklch_to_hex ---

def test_black_conversion():
    """oklch(0 0 0) should be black (#000000)."""
    result = oklch_to_hex("oklch(0 0 0)")
    assert result == "#000000"


def test_white_conversion():
    """oklch(1 0 0) should be close to white (#ffffff)."""
    result = oklch_to_hex("oklch(1 0 0)")
    assert result == "#ffffff"


def test_mid_gray():
    """oklch with L ~0.6 and no chroma is a gray."""
    result = oklch_to_hex("oklch(0.6 0 0)")
    # Should be some gray, same R/G/B values
    r = int(result[1:3], 16)
    g = int(result[3:5], 16)
    b = int(result[5:7], 16)
    assert r == g == b
    # Should be roughly in mid-range
    assert 80 < r < 200


def test_returns_hex_format():
    """Result is always a 7-character hex string starting with #."""
    result = oklch_to_hex("oklch(0.7 0.15 180)")
    assert result.startswith("#")
    assert len(result) == 7


# --- hex_to_oklch ---

def test_hex_to_oklch_black():
    """Black hex should produce oklch(0, 0, 0)."""
    result = hex_to_oklch("#000000")
    assert "oklch(" in result
    l, c, h = parse_oklch(result)
    assert l == pytest.approx(0.0, abs=0.01)
    assert c == pytest.approx(0.0, abs=0.01)


def test_hex_to_oklch_white():
    """White hex should produce L close to 1."""
    result = hex_to_oklch("#ffffff")
    l, c, h = parse_oklch(result)
    assert l == pytest.approx(1.0, abs=0.02)
    assert c == pytest.approx(0.0, abs=0.01)


def test_round_trip_approximate():
    """oklch -> hex -> oklch should be approximately consistent."""
    original = "oklch(0.6 0.1 200)"
    hex_val = oklch_to_hex(original)
    back = hex_to_oklch(hex_val)
    l_orig, c_orig, h_orig = parse_oklch(original)
    l_back, c_back, h_back = parse_oklch(back)
    # Allow some rounding error from 8-bit quantization
    assert l_back == pytest.approx(l_orig, abs=0.05)
    assert c_back == pytest.approx(c_orig, abs=0.05)
