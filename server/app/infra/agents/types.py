"""Type definitions for agent-related structures."""

from typing import Any, TypedDict


class TResponseInputItem(TypedDict, total=False):
    """Type definition for response input items used in agent conversations.

    This replaces the TResponseInputItem from openai-agents package.
    Compatible with litellm message format.
    """

    role: str  # "user", "assistant", "system", etc.
    content: (
        str | list[dict[str, Any]]
    )  # Message content - can be string or structured content
