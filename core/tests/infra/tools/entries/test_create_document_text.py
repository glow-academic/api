"""Tests for create_document_text — creates text + upload entry chain."""

import uuid

import pytest

from app.infra.tools.entries.create_document_text import (
    CreateDocumentTextResult,
    create_document_text,
)

pytestmark = pytest.mark.asyncio


async def test_creates_full_entry_chain(conn, redis_client, session_id, tmp_path):
    """create_document_text returns all four IDs from the entry chain."""
    result = await create_document_text(
        conn,
        redis_client,
        content="Hello, world!",
        session_id=session_id,
        upload_folder=tmp_path,
    )

    assert isinstance(result, CreateDocumentTextResult)
    assert result.texts_resource_id is not None
    assert result.text_entry_id is not None
    assert result.upload_id is not None
    assert result.text_upload_id is not None


async def test_writes_text_file_to_disk(conn, redis_client, session_id, tmp_path):
    """The content is written as a .txt file under upload_folder/text/."""
    content = "Test content for document text"
    result = await create_document_text(
        conn,
        redis_client,
        content=content,
        session_id=session_id,
        upload_folder=tmp_path,
    )

    text_dir = tmp_path / "text"
    assert text_dir.is_dir()
    txt_files = list(text_dir.glob("*.txt"))
    assert len(txt_files) >= 1

    # At least one file should contain the content
    found = any(f.read_text(encoding="utf-8") == content for f in txt_files)
    assert found, "Expected content not found in any text file"


async def test_returns_unique_ids_per_call(conn, redis_client, session_id, tmp_path):
    """Two calls produce distinct IDs for every field."""
    r1 = await create_document_text(
        conn,
        redis_client,
        content="First text",
        session_id=session_id,
        upload_folder=tmp_path,
    )
    r2 = await create_document_text(
        conn,
        redis_client,
        content="Second text",
        session_id=session_id,
        upload_folder=tmp_path,
    )

    assert r1.texts_resource_id != r2.texts_resource_id
    assert r1.text_entry_id != r2.text_entry_id
    assert r1.upload_id != r2.upload_id
    assert r1.text_upload_id != r2.text_upload_id


async def test_result_dataclass_is_frozen():
    """CreateDocumentTextResult is a frozen dataclass — fields are immutable."""
    result = CreateDocumentTextResult(
        texts_resource_id=uuid.uuid4(),
        text_entry_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        text_upload_id=uuid.uuid4(),
    )

    with pytest.raises(AttributeError):
        result.texts_resource_id = uuid.uuid4()
