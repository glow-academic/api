"""Tests for save_text_upload."""

from tests.helpers import nonexistent_id

from app.infra.tools.entries.save_text_upload import save_text_upload


def test_returns_relative_path(tmp_path):
    upload_id = nonexistent_id()
    result = save_text_upload("hello", upload_id, tmp_path)

    assert result == f"text/{upload_id}.txt"


def test_creates_file(tmp_path):
    upload_id = nonexistent_id()
    save_text_upload("hello world", upload_id, tmp_path)

    full_path = tmp_path / "text" / f"{upload_id}.txt"

    assert full_path.exists()
    assert full_path.read_text(encoding="utf-8") == "hello world"


def test_creates_subfolder(tmp_path):
    upload_id = nonexistent_id()
    save_text_upload("content", upload_id, tmp_path)

    assert (tmp_path / "text").is_dir()
