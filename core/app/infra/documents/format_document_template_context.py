"""Format document template context for agent input."""

from typing import Any

from app.infra.agents.types import TResponseInputItem


def build_document_context_lines(
    document_name: str | None = None,
    document_description: str | None = None,
    department_name: str | None = None,
) -> list[str]:
    """Build the non-empty document context lines."""
    context_lines: list[str] = []

    if document_name:
        context_lines.append(f"Document Name: {document_name}")

    if document_description:
        context_lines.append(f"Document Description: {document_description}")

    if department_name:
        context_lines.append(f"Department: {department_name}")

    return context_lines


def format_template_field_info(row: dict[str, Any]) -> str:
    """Format one template field row as agent-facing guidance text."""
    return (
        f"This is the {row['param_name']} ({row.get('param_description', '')}) for this chat: {row['item_name']}. "
        f"Description: {row.get('item_description', '')}."
    )


def build_template_fields_content(fields: list[dict[str, Any]]) -> str:
    """Build the combined field-information content block."""
    formatted_items = [format_template_field_info(row) for row in fields]
    return "The following is the parameter item information:\n" + "\n".join(
        formatted_items
    )


def format_document_template_context(
    document_name: str | None = None,
    document_description: str | None = None,
    department_name: str | None = None,
    fields: list[dict[str, Any]] | None = None,
) -> list[TResponseInputItem]:
    """
    Format document template context as list of TResponseInputItem.

    Args:
        document_name: Optional document name
        document_description: Optional document description
        department_name: Optional department name
        fields: Optional list of field dicts with keys: item_name, item_description,
                param_name, param_description

    Returns:
        List of TResponseInputItem formatted for agent input
    """
    input_items: list[TResponseInputItem] = []

    # Build document context message
    context_parts = build_document_context_lines(
        document_name=document_name,
        document_description=document_description,
        department_name=department_name,
    )

    if context_parts:
        document_context: TResponseInputItem = {
            "role": "user",
            "content": "Document Context:\n" + "\n".join(context_parts),
        }
        input_items.append(document_context)

    # Add fields information if provided
    if fields:
        content = build_template_fields_content(fields)
        fields_info = {
            "role": "user",
            "content": content,
        }
        input_items.append(fields_info)

    return input_items
