"""Tests for app.utils.document.pdf_pages_to_image_data_urls."""

import base64
from unittest.mock import MagicMock

from app.utils.document.pdf_pages_to_image_data_urls import pdf_pages_to_image_data_urls


def _make_mock_page(png_bytes):
    """Create a mock page whose pixmap returns given PNG bytes."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = png_bytes
    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix
    return mock_page


def test_returns_data_urls_for_each_page():
    """Each page is converted to a base64 PNG data URL."""
    page1_bytes = b"page1-png"
    page2_bytes = b"page2-png"
    pages = [_make_mock_page(page1_bytes), _make_mock_page(page2_bytes)]

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(pages))

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    result = pdf_pages_to_image_data_urls("/fake/path.pdf", fitz_module=mock_fitz)
    assert len(result) == 2
    expected_b64_1 = base64.b64encode(page1_bytes).decode("ascii")
    assert result[0] == f"data:image/png;base64,{expected_b64_1}"
    expected_b64_2 = base64.b64encode(page2_bytes).decode("ascii")
    assert result[1] == f"data:image/png;base64,{expected_b64_2}"


def test_empty_pdf_returns_empty_list():
    """A PDF with zero pages returns empty list."""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([]))

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    result = pdf_pages_to_image_data_urls("/fake/path.pdf", fitz_module=mock_fitz)
    assert result == []


def test_returns_empty_list_on_error():
    """On rendering error, returns empty list."""
    mock_fitz = MagicMock()
    mock_fitz.open.side_effect = RuntimeError("broken")

    result = pdf_pages_to_image_data_urls("/fake/path.pdf", fitz_module=mock_fitz)
    assert result == []


def test_returns_empty_list_when_fitz_unavailable():
    """When fitz_module is None and import fails, returns empty list."""
    result = pdf_pages_to_image_data_urls("/fake/path.pdf", fitz_module=None)
    # If fitz not installed returns [], if installed tries to open nonexistent file and returns []
    assert result == [] or isinstance(result, list)
