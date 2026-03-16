"""Store the Runner result object locally for immediate cancel."""

from app.infra.globals import get_active_results_dict


async def store_active_result(chat_id: str, result: object) -> None:
    """Store the Runner result object locally for immediate cancel."""
    active_results = get_active_results_dict()
    if chat_id not in active_results:
        active_results[chat_id] = {}
    active_results[chat_id]["result"] = result
