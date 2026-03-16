"""Convert input_items to litellm message format."""

from typing import Any

from app.infra.agents.types import TResponseInputItem


def format_messages_for_litellm(
    input_items: list[TResponseInputItem],
) -> list[dict[str, Any]]:
    """Convert input_items to litellm message format.

    Args:
        input_items: List of TResponseInputItem

    Returns:
        List of message dictionaries for litellm
    """
    messages: list[dict[str, Any]] = []

    for item in input_items:
        role = item.get("role", "user")
        content = item.get("content", "")

        # Handle audio file paths if present
        if isinstance(content, str) and "Audio file to process:" in content:
            # For now, just include as text - litellm can handle file paths
            # TODO: Convert to proper audio format if needed
            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )
        else:
            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    return messages
