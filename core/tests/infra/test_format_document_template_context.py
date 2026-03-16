"""Tests for pure document template context helpers."""

from app.infra.documents.format_document_template_context import (
    build_document_context_lines,
    build_template_fields_content,
    format_document_template_context,
    format_template_field_info,
)


def test_build_document_context_lines_skips_empty_values():
    lines = build_document_context_lines(
        document_name="Offer Letter",
        document_description=None,
        department_name="HR",
    )

    assert lines == [
        "Document Name: Offer Letter",
        "Department: HR",
    ]


def test_format_template_field_info_includes_optional_descriptions():
    line = format_template_field_info(
        {
            "param_name": "candidate_name",
            "param_description": "full legal name",
            "item_name": "Candidate Record",
            "item_description": "Primary applicant profile",
        }
    )

    assert line == (
        "This is the candidate_name (full legal name) for this chat: Candidate Record. "
        "Description: Primary applicant profile."
    )


def test_build_template_fields_content_joins_multiple_rows():
    content = build_template_fields_content(
        [
            {
                "param_name": "company",
                "param_description": "employer name",
                "item_name": "Company Context",
                "item_description": "Hiring organization",
            },
            {
                "param_name": "start_date",
                "item_name": "Offer Dates",
            },
        ]
    )

    assert content.startswith("The following is the parameter item information:\n")
    assert (
        "This is the company (employer name) for this chat: Company Context." in content
    )
    assert (
        "This is the start_date () for this chat: Offer Dates. Description: ."
        in content
    )


def test_format_document_template_context_returns_context_and_fields_messages():
    items = format_document_template_context(
        document_name="Offer Letter",
        document_description="Employment contract template",
        department_name="HR",
        fields=[
            {
                "param_name": "candidate_name",
                "item_name": "Candidate",
            }
        ],
    )

    assert items[0] == {
        "role": "user",
        "content": (
            "Document Context:\n"
            "Document Name: Offer Letter\n"
            "Document Description: Employment contract template\n"
            "Department: HR"
        ),
    }
    assert items[1]["role"] == "user"
    assert "candidate_name" in items[1]["content"]
