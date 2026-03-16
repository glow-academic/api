"""Tests for MIME helpers."""

from app.utils.mime.get_content_type import get_content_type
from app.utils.mime.infer_mime_from_name import infer_mime_from_name


def test_infer_mime_uses_override_map_for_editor_friendly_extensions():
    assert infer_mime_from_name("component.tsx") == "text/typescript; charset=utf-8"


def test_infer_mime_falls_back_when_filename_is_missing():
    assert infer_mime_from_name("") == "application/octet-stream"


def test_get_content_type_trusts_specific_stored_mime():
    assert get_content_type("document.pdf", "application/pdf") == "application/pdf"


def test_get_content_type_replaces_generic_mime_with_inferred_value():
    assert (
        get_content_type("script.tsx", "application/octet-stream")
        == "text/typescript; charset=utf-8"
    )
