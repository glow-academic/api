"""Format problem statement as chat scenario message."""

from app.infra.agents.types import TResponseInputItem


def format_chat_scenario(problem_statement: str | None) -> TResponseInputItem:
    """
    Format a problem statement as a chat scenario message.

    Args:
        problem_statement: The scenario problem statement text (can be None)

    Returns:
        Formatted message dict for chat input
    """
    # Handle None values defensively
    statement = problem_statement if problem_statement is not None else ""
    return {
        "role": "developer",
        "content": f"The following is the scenario for the chat: {statement}",
    }
