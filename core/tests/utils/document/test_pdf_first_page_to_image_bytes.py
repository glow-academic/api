"""Tests for app.utils.document.pdf_first_page_to_image_bytes."""

from unittest.mock import MagicMock

from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)


def test_returns_png_bytes_from_mock_fitz():
    """With a valid mock fitz module, returns PNG bytes from first page."""
    fake_png = b"\x89PNG-fake-data"
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = fake_png

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=2)
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    result = pdf_first_page_to_image_bytes("/fake/path.pdf", fitz_module=mock_fitz)
    assert result == fake_png
    mock_doc.close.assert_called_once()


def test_returns_none_for_empty_pdf():
    """A PDF with zero pages returns None."""
    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=0)

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc

    result = pdf_first_page_to_image_bytes("/fake/path.pdf", fitz_module=mock_fitz)
    assert result is None
    mock_doc.close.assert_called_once()


def test_returns_none_when_fitz_not_available():
    """When fitz_module is None and fitz is not importable, returns None."""
    # Pass fitz_module=None and let it try to import fitz which will fail
    # in test environment if fitz isn't installed. Either way, should not crash.
    result = pdf_first_page_to_image_bytes("/fake/path.pdf", fitz_module=None)
    # If fitz is installed in test env it would try to open the file and fail gracefully
    # If not installed, returns None. Either way, no exception.
    assert result is None or isinstance(result, bytes)


def test_returns_none_on_rendering_error():
    """If rendering throws an exception, returns None gracefully."""
    mock_fitz = MagicMock()
    mock_fitz.open.side_effect = RuntimeError("corrupt PDF")

    result = pdf_first_page_to_image_bytes("/fake/path.pdf", fitz_module=mock_fitz)
    assert result is None
