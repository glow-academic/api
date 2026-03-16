"""Tests for file writer utilities using the real test database."""

from uuid import UUID

import pytest

from app.utils.storage.file_writer import (
    read_text_file,
    write_json_file,
    write_text_file,
)

pytestmark = pytest.mark.asyncio


async def test_write_text_file_persists_file_and_upload_row(conn, session_id, tmp_path):
    content = "hello from test storage"

    upload_id = await write_text_file(
        conn,
        session_id,
        content,
        upload_folder=tmp_path,
    )
    row = await conn.fetchrow(
        """
        SELECT file_path, mime_type, size, session_id
        FROM uploads_entry
        WHERE id = $1
        """,
        upload_id,
    )

    assert row is not None
    assert row["mime_type"] == "text/plain"
    assert row["size"] == len(content.encode("utf-8"))
    assert row["session_id"] == session_id
    assert read_text_file(row["file_path"], upload_folder=tmp_path) == content

    (tmp_path / row["file_path"]).unlink(missing_ok=True)


async def test_write_json_file_serializes_payload_and_creates_upload_record(
    conn, session_id, tmp_path
):
    payload = {"id": UUID("00000000-0000-0000-0000-000000000123"), "ok": True}

    upload_id = await write_json_file(
        conn,
        session_id,
        payload,
        subdir="test-json",
        upload_folder=tmp_path,
    )
    row = await conn.fetchrow(
        """
        SELECT file_path, mime_type, size, session_id
        FROM uploads_entry
        WHERE id = $1
        """,
        upload_id,
    )

    assert row is not None
    assert row["mime_type"] == "application/json"
    assert row["session_id"] == session_id

    file_path = tmp_path / row["file_path"]
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == (
        '{"id": "00000000-0000-0000-0000-000000000123", "ok": true}'
    )
    assert row["size"] == file_path.stat().st_size

    file_path.unlink(missing_ok=True)
