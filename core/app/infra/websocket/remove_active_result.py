"""Remove stored Runner result for a chat."""

from app.infra.globals import get_active_results_dict


async def remove_active_result(chat_id: str) -> None:
    """Remove stored Runner result for a chat."""
    active_results = get_active_results_dict()
    active_results.pop(chat_id, None)
