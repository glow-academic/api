"""Tests for sanitize_icon_value (icon-value write-side XSS defence)."""

import pytest

from app.utils.svg_safety import sanitize_icon_value


def test_plain_name_identifier_passes_through():
    assert sanitize_icon_value("robot") == "robot"


def test_plain_name_is_stripped():
    assert sanitize_icon_value("  star  ") == "star"


def test_valid_svg_kept_intact():
    out = sanitize_icon_value(
        '<svg viewBox="0 0 24 24"><path d="M4 14a1 1 0 0 1-.78z" /></svg>'
    )
    assert out.startswith("<svg")
    assert 'viewBox="0 0 24 24"' in out
    assert "<path" in out
    assert 'd="M4 14a1 1 0 0 1-.78z"' in out


def test_rejects_malformed_trailing_img():
    # `<svg></svg><img src=x onerror=alert(1)>` is not well-formed XML
    # (unquoted attrs / unclosed void tag) → rejected (HTTP 400).
    with pytest.raises(ValueError):
        sanitize_icon_value("<svg></svg><img src=x onerror=alert(1)>")


def test_drops_sibling_markup_after_svg():
    # Well-formed sibling markup after the <svg> is dropped (only the svg
    # subtree is kept and re-serialized).
    out = sanitize_icon_value('<svg><path d="M0 0z"/></svg><g onload="x"/>')
    assert out.startswith("<svg")
    assert "onload" not in out
    assert out.count("<svg") == 1


def test_strips_svg_onload_handler():
    out = sanitize_icon_value('<svg onload="alert(1)"><path d="M0 0z"/></svg>')
    assert "onload" not in out
    assert "<path" in out


def test_strips_script_element():
    out = sanitize_icon_value('<svg><script>alert(1)</script><path d="M0 0z"/></svg>')
    assert "<script" not in out
    assert "alert" not in out
    assert "<path" in out


def test_strips_foreign_object():
    out = sanitize_icon_value(
        '<svg><foreignObject><body onload="alert(1)"/></foreignObject>'
        '<path d="M0 0z"/></svg>'
    )
    assert "foreignobject" not in out.lower()
    assert "onload" not in out


def test_strips_external_href_on_use():
    out = sanitize_icon_value('<svg><use href="https://evil/x.svg#a"/></svg>')
    assert "https://evil" not in out
    assert "href" not in out


def test_keeps_internal_fragment_href():
    out = sanitize_icon_value('<svg><use href="#icon-a"/></svg>')
    assert 'href="#icon-a"' in out


def test_strips_inline_style():
    out = sanitize_icon_value(
        '<svg style="background:url(javascript:alert(1))"><path d="M0 0z"/></svg>'
    )
    assert "style" not in out
    assert "javascript" not in out


def test_markup_without_svg_rejected():
    with pytest.raises(ValueError):
        sanitize_icon_value("<img src=x onerror=alert(1)>")


def test_empty_rejected():
    with pytest.raises(ValueError):
        sanitize_icon_value("   ")


def test_malformed_markup_rejected():
    with pytest.raises(ValueError):
        sanitize_icon_value("<svg><path")
