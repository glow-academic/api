"""Tests for pure document content shaping helpers."""

from app.infra.documents.format_document_info import (
    _format_template_args_notice,
    build_document_content_items,
)


def test_format_template_args_notice_handles_json_string_schema():
    notice = _format_template_args_notice(
        '{"name":"Offer Letter","fields":[{"name":"candidate_name","type":"string","required":true,"description":"Person to hire"}]}'
    )

    assert "Offer Letter" in notice
    assert "candidate_name: string (required)" in notice
    assert "Person to hire" in notice


def test_build_document_content_items_orders_pdf_image_then_text():
    items = build_document_content_items(
        {
            "name": "Spec",
            "file_path": "docs/spec.pdf",
            "mime_type": "application/pdf",
        },
        doc_index=2,
        text_pages=["Page one", "Page two"],
        image_urls=["data:image/png;base64,aaa"],
        show_images=True,
    )

    assert items[0] == {
        "type": "input_image",
        "detail": "auto",
        "image_url": "data:image/png;base64,aaa",
    }
    assert items[1]["type"] == "input_text"
    assert "--- doc2-text-page1 ---" in items[1]["text"]
    assert items[1]["text"].endswith("Page one")
    assert items[2]["type"] == "input_text"
    assert "--- doc2-text-page2 ---" in items[2]["text"]
    assert items[2]["text"].endswith("Page two")


def test_build_document_content_items_includes_template_notice_once():
    items = build_document_content_items(
        {
            "name": "Template",
            "file_path": "docs/template.pdf",
            "mime_type": "application/pdf",
            "template": True,
            "template_args": {
                "name": "Intake Form",
                "fields": [{"name": "company", "type": "string", "required": True}],
            },
        },
        doc_index=1,
        text_pages=["First page", "Second page"],
        show_images=False,
    )

    assert "TEMPLATE DOCUMENT" in items[0]["text"]
    assert "company: string (required)" in items[0]["text"]
    assert "TEMPLATE DOCUMENT" not in items[1]["text"]


def test_build_document_content_items_returns_single_text_item_for_plain_text():
    items = build_document_content_items(
        {
            "name": "Notes",
            "file_path": "docs/notes.txt",
            "mime_type": "text/plain",
        },
        doc_index=3,
        text_content="hello world",
    )

    assert items == [
        {
            "type": "input_text",
            "text": (
                "--- doc3-text-page1 ---\n"
                "Name: Notes\n"
                "File Type: text/plain\n"
                "Tags: None\n"
                "Content:\n"
                "hello world"
            ),
        }
    ]


def test_build_document_content_items_returns_image_only_for_image_document():
    items = build_document_content_items(
        {
            "name": "Preview",
            "file_path": "docs/preview.png",
            "mime_type": "image/png",
        },
        doc_index=1,
        image_urls=["data:image/png;base64,bbb"],
        show_images=True,
    )

    assert items == [
        {
            "type": "input_image",
            "detail": "auto",
            "image_url": "data:image/png;base64,bbb",
        }
    ]
