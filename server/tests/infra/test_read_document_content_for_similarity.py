"""Tests for document similarity content extraction."""

import pypdf  # type: ignore

from app.infra.documents.read_document_content_for_similarity import (
    read_document_content_for_similarity,
)


def test_reads_plain_text_from_supplied_upload_root(tmp_path):
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    path = text_dir / "sample.txt"
    path.write_text("  Similarity body here  ", encoding="utf-8")

    result = read_document_content_for_similarity(
        "text/sample.txt",
        upload_folder=tmp_path,
    )

    assert result == "Similarity body here"


def test_returns_empty_string_for_missing_file(tmp_path):
    result = read_document_content_for_similarity(
        "text/missing.txt",
        upload_folder=tmp_path,
    )

    assert result == ""


def test_reads_pdf_pages_without_crashing(tmp_path):
    pdf_dir = tmp_path / "docs"
    pdf_dir.mkdir()
    path = pdf_dir / "blank.pdf"

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as file:
        writer.write(file)

    result = read_document_content_for_similarity(
        "docs/blank.pdf",
        upload_folder=tmp_path,
    )

    assert result == ""
