"""Tests for create_document_file — copies source file and creates entry chain."""

import uuid

import pytest

from app.infra.tools.entries.create_document_file import (
    CreateDocumentFileResult,
    create_document_file,
)

pytestmark = pytest.mark.asyncio


def _make_source_file(tmp_path, name="sample.pdf", content=b"fake pdf content"):
    """Create a temporary source file and return its path."""
    source = tmp_path / "sources" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    return source


async def test_creates_full_entry_chain(conn, redis_client, session_id, tmp_path):
    """create_document_file returns all four IDs from the entry chain."""
    source = _make_source_file(tmp_path)
    upload_folder = tmp_path / "uploads"
    upload_folder.mkdir()

    result = await create_document_file(
        conn,
        redis_client,
        source_path=source,
        mime_type="application/pdf",
        session_id=session_id,
        upload_folder=upload_folder,
    )

    assert isinstance(result, CreateDocumentFileResult)
    assert result.files_resource_id is not None
    assert result.file_entry_id is not None
    assert result.upload_id is not None
    assert result.file_upload_id is not None


async def test_copies_source_file_to_upload_folder(conn, redis_client, session_id, tmp_path):
    """The source file is copied (not moved) into upload_folder."""
    content = b"important document bytes"
    source = _make_source_file(tmp_path, name="report.docx", content=content)
    upload_folder = tmp_path / "uploads"
    upload_folder.mkdir()

    await create_document_file(
        conn,
        redis_client,
        source_path=source,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        session_id=session_id,
        upload_folder=upload_folder,
    )

    # Source still exists (copy, not move)
    assert source.exists()

    # A file with .docx extension should exist in upload_folder
    copied_files = list(upload_folder.glob("*.docx"))
    assert len(copied_files) == 1
    assert copied_files[0].read_bytes() == content


async def test_returns_unique_ids_per_call(conn, redis_client, session_id, tmp_path):
    """Two calls produce distinct IDs."""
    upload_folder = tmp_path / "uploads"
    upload_folder.mkdir()

    s1 = _make_source_file(tmp_path, name="a.txt", content=b"aaa")
    s2 = _make_source_file(tmp_path, name="b.txt", content=b"bbb")

    r1 = await create_document_file(
        conn,
        redis_client,
        source_path=s1,
        mime_type="text/plain",
        session_id=session_id,
        upload_folder=upload_folder,
    )
    r2 = await create_document_file(
        conn,
        redis_client,
        source_path=s2,
        mime_type="text/plain",
        session_id=session_id,
        upload_folder=upload_folder,
    )

    assert r1.files_resource_id != r2.files_resource_id
    assert r1.file_entry_id != r2.file_entry_id
    assert r1.upload_id != r2.upload_id
    assert r1.file_upload_id != r2.file_upload_id


async def test_result_dataclass_is_frozen():
    """CreateDocumentFileResult is a frozen dataclass — fields are immutable."""
    result = CreateDocumentFileResult(
        files_resource_id=uuid.uuid4(),
        file_entry_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        file_upload_id=uuid.uuid4(),
    )

    with pytest.raises(AttributeError):
        result.files_resource_id = uuid.uuid4()
