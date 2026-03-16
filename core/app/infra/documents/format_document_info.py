"""Build a structured list of per-document, per-page text and optional images."""

import base64
import json
import os
from typing import Any

from openai.types.responses.response_input_item_param import Message
from openai.types.responses.response_input_message_content_list_param import (
    ResponseInputMessageContentListParam,
)

from app.infra.agents.types import TResponseInputItem
from app.infra.globals import UPLOAD_FOLDER
from app.utils.document.pdf_pages_to_image_data_urls import pdf_pages_to_image_data_urls
from app.utils.document.read_pdf_text_pages import read_pdf_text_pages
from app.utils.document.read_text_file import read_text_file


def _format_template_args_notice(template_args: Any) -> str:
    """Format template arguments schema as a readable notice.

    Args:
        template_args: Template args dict with 'name' and 'fields' keys, or JSON string

    Returns:
        Formatted string describing the template and its required arguments
    """
    if not template_args:
        return ""

    # Parse template_args if it's a string
    parsed_args: dict[str, Any] | None = None
    if isinstance(template_args, str):
        try:
            parsed_args = json.loads(template_args)
        except json.JSONDecodeError:
            return ""
    elif isinstance(template_args, dict):
        parsed_args = template_args
    else:
        return ""

    if not parsed_args:
        return ""

    schema_name = parsed_args.get("name", "Template")
    fields = parsed_args.get("fields", [])

    if not fields:
        return f"⚠️ TEMPLATE DOCUMENT: This is a template document ({schema_name}) with template arguments that need to be filled.\n\n"

    # Build field descriptions
    field_descriptions = []
    for field in fields:
        field_name = field.get("name", "")
        field_type = field.get("type", "string")
        required = field.get("required", False)
        description = field.get("description", "")
        placeholder = field.get("placeholder", "")
        required_str = " (required)" if required else " (optional)"

        field_desc = f"  - {field_name}: {field_type}{required_str}"
        if description:
            field_desc += f"\n    Description: {description}"
        if placeholder:
            field_desc += f"\n    Example: {placeholder}"

        field_descriptions.append(field_desc)

    fields_text = "\n".join(field_descriptions)

    notice = (
        f"⚠️ TEMPLATE DOCUMENT: This is a template document ({schema_name}) with the following template arguments:\n\n"
        f"{fields_text}\n\n"
    )

    return notice


def build_document_content_items(
    document: dict[str, Any],
    *,
    doc_index: int,
    text_pages: list[str] | None = None,
    image_urls: list[str] | None = None,
    text_content: str | None = None,
    show_images: bool = False,
) -> ResponseInputMessageContentListParam:
    """Build message content items for one document from already-loaded content."""
    if not document or not document.get("file_path"):
        return []

    content_items: ResponseInputMessageContentListParam = []
    tags_display = ""
    file_path = document["file_path"]
    mime_lower = (document.get("mime_type") or "").lower()

    template_notice = ""
    if document.get("template") and document.get("template_args"):
        template_notice = _format_template_args_notice(document.get("template_args"))

    is_pdf = file_path.lower().endswith(".pdf") or "pdf" in mime_lower
    is_image = mime_lower.startswith("image/") or file_path.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif")
    )

    if is_pdf:
        loaded_text_pages = text_pages or []
        loaded_image_urls = image_urls or []
        total_pages = (
            max(len(loaded_text_pages), len(loaded_image_urls))
            if show_images
            else len(loaded_text_pages)
        )
        for page_num in range(total_pages):
            if show_images and page_num < len(loaded_image_urls):
                content_items.append(
                    {
                        "type": "input_image",
                        "detail": "auto",
                        "image_url": loaded_image_urls[page_num],
                    }
                )

            page_text = (
                loaded_text_pages[page_num] if page_num < len(loaded_text_pages) else ""
            )
            header = (
                f"--- doc{doc_index}-text-page{page_num + 1} ---\n"
                f"Name: {document['name']}\n"
                f"File Type: {document.get('mime_type', 'unknown')}\n"
                f"Tags: {tags_display if tags_display else 'None'}\n"
                f"Content:\n"
            )
            content_items.append(
                {
                    "type": "input_text",
                    "text": header
                    + (template_notice if page_num == 0 else "")
                    + page_text,
                }
            )
        return content_items

    if is_image:
        if show_images and image_urls:
            content_items.append(
                {
                    "type": "input_image",
                    "detail": "auto",
                    "image_url": image_urls[0],
                }
            )
        return content_items

    header = (
        f"--- doc{doc_index}-text-page1 ---\n"
        f"Name: {document['name']}\n"
        f"File Type: {document.get('mime_type', 'unknown')}\n"
        f"Tags: {tags_display if tags_display else 'None'}\n"
        f"Content:\n"
    )
    content_items.append(
        {
            "type": "input_text",
            "text": header + template_notice + (text_content or ""),
        }
    )
    return content_items


def format_document_info(
    documents: list[dict[str, Any]], show_images: bool = False
) -> TResponseInputItem:
    """Build a structured list of per-document, per-page text and optional images.

    Order per document: docN-image-pageM, then docN-text-pageM. If images are
    unavailable or disabled, only include docN-text-pageM.

    Args:
        documents: List of dicts with keys: id, name, file_path, mime_type, template (bool), template_args (dict)
        show_images: Whether to include images in the output

    Returns:
        TResponseInputItem formatted for agent input
    """
    if not documents:
        # Return a minimal message if no documents provided
        msg: Message = {
            "role": "user",
            "content": [{"type": "input_text", "text": "No documents provided"}],
        }
        return msg

    content_items: ResponseInputMessageContentListParam = []

    for doc_index, document in enumerate(documents, start=1):
        if not document:
            # Skip missing docs quietly to keep order for others
            continue

        # Skip documents without a file_path (no upload or upload has no file)
        file_path = document.get("file_path")
        if not file_path:
            continue

        full_path = os.path.join(UPLOAD_FOLDER, file_path)
        mime_lower = (document.get("mime_type") or "").lower()

        is_pdf = file_path.lower().endswith(".pdf") or "pdf" in mime_lower
        is_image = mime_lower.startswith("image/") or file_path.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".gif")
        )

        if is_pdf:
            # Per-page text via pypdf
            text_pages = read_pdf_text_pages(full_path)
            # Optional images via PyMuPDF if enabled
            image_urls = pdf_pages_to_image_data_urls(full_path) if show_images else []

            content_items.extend(
                build_document_content_items(
                    document,
                    doc_index=doc_index,
                    text_pages=text_pages,
                    image_urls=image_urls,
                    show_images=show_images,
                )
            )
        elif is_image:
            # For image files, include the image only (no text)
            if show_images:
                try:
                    with open(full_path, "rb") as img_file:  # noqa: PTH123
                        img_bytes = img_file.read()
                    b64 = base64.b64encode(img_bytes).decode("ascii")
                    # Prefer MIME from record; fallback based on extension
                    mime_type = document.get("mime_type")
                    mime = (
                        mime_type
                        if (mime_type and mime_type.startswith("image/"))
                        else None
                    )
                    if not mime:
                        if file_path.lower().endswith(".png"):
                            mime = "image/png"
                        elif file_path.lower().endswith((".jpg", ".jpeg")):
                            mime = "image/jpeg"
                        elif file_path.lower().endswith(".webp"):
                            mime = "image/webp"
                        elif file_path.lower().endswith(".gif"):
                            mime = "image/gif"
                        else:
                            mime = "image/png"
                    content_items.extend(
                        build_document_content_items(
                            document,
                            doc_index=doc_index,
                            image_urls=[f"data:{mime};base64,{b64}"],
                            show_images=show_images,
                        )
                    )
                except Exception:
                    # If reading fails, skip the image silently
                    pass
            # If show_images is False, we add nothing for pure image docs
        else:
            # Treat other files as a single-page text document
            content = read_text_file(full_path)
            content_items.extend(
                build_document_content_items(
                    document,
                    doc_index=doc_index,
                    text_content=content,
                )
            )

    if not content_items:
        # Fallback to a minimal text item if nothing could be built
        content_items.append({"type": "input_text", "text": "No documents provided"})

    result_msg: Message = {"role": "developer", "content": content_items}
    return result_msg
