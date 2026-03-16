"""Business calculations for benchmark test artifacts."""


def compute_test_status(
    num_chats: int | None,
    num_chats_completed: int | None,
) -> str:
    """Compute a minimal status label from chat completion counts."""
    total = num_chats or 0
    done = num_chats_completed or 0

    if total <= 0:
        return "pending"
    if done <= 0:
        return "running"
    if done >= total:
        return "completed"
    return "running"
