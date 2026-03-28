"""Tests for app.utils.document.read_pdf_text_pages."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from app.utils.document.read_pdf_text_pages import read_pdf_text_pages


def _make_mock_page(text):
    """Create a mock PDF page that returns given text."""
    page = MagicMock()
    page.extract_text.return_value = text
    return page


def test_returns_list_of_page_texts():
    """Extracted text for each page is returned as a list."""
    pages = [_make_mock_page("Page one text"), _make_mock_page("Page two text")]
    mock_reader = MagicMock()
    mock_reader.pages = pages

    with patch("app.utils.document.read_pdf_text_pages.pypdf") as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        with patch("builtins.open", mock_open(read_data=b"")):
            result = read_pdf_text_pages("/fake/path.pdf")

    assert result == ["Page one text", "Page two text"]


def test_strips_page_text():
    """Whitespace around page text is stripped."""
    pages = [_make_mock_page("  some text  \n")]
    mock_reader = MagicMock()
    mock_reader.pages = pages

    with patch("app.utils.document.read_pdf_text_pages.pypdf") as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        with patch("builtins.open", mock_open(read_data=b"")):
            result = read_pdf_text_pages("/fake/path.pdf")

    assert result == ["some text"]


def test_none_text_becomes_empty_string():
    """A page that returns None for extract_text becomes empty string."""
    pages = [_make_mock_page(None)]
    mock_reader = MagicMock()
    mock_reader.pages = pages

    with patch("app.utils.document.read_pdf_text_pages.pypdf") as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        with patch("builtins.open", mock_open(read_data=b"")):
            result = read_pdf_text_pages("/fake/path.pdf")

    assert result == [""]


def test_empty_pdf_returns_empty_list():
    """A PDF with no pages returns empty list."""
    mock_reader = MagicMock()
    mock_reader.pages = []

    with patch("app.utils.document.read_pdf_text_pages.pypdf") as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        with patch("builtins.open", mock_open(read_data=b"")):
            result = read_pdf_text_pages("/fake/path.pdf")

    assert result == []
