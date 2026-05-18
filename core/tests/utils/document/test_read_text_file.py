"""Tests for app.utils.document.read_text_file."""

import os
import tempfile

import pytest

from app.utils.document.read_text_file import read_text_file


def test_reads_utf8_file():
    """A standard UTF-8 text file is read and stripped."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("  hello world  \n")
        path = f.name
    try:
        assert read_text_file(path) == "hello world"
    finally:
        os.unlink(path)


def test_reads_latin1_fallback():
    """A file with latin-1 bytes not valid in UTF-8 falls back to latin-1."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        # \xe9 is 'e-acute' in latin-1 but invalid as standalone UTF-8 byte
        f.write(b"caf\xe9")
        path = f.name
    try:
        result = read_text_file(path)
        assert "caf" in result
    finally:
        os.unlink(path)


def test_empty_file_returns_empty_string():
    """An empty file yields empty string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("")
        path = f.name
    try:
        assert read_text_file(path) == ""
    finally:
        os.unlink(path)


def test_file_not_found_raises():
    """A non-existent path raises an error."""
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        read_text_file("/nonexistent/path/to/file.txt")


def test_strips_whitespace():
    """Leading/trailing whitespace including newlines is stripped."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n\n  content here  \n\n")
        path = f.name
    try:
        assert read_text_file(path) == "content here"
    finally:
        os.unlink(path)
