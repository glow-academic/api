"""Business logic for benchmark artifact — pure Python, no SQL."""


def compute_benchmark_eval_status(
    has_passed: bool,
    completed_invocations: int,
    total_invocations: int,
) -> str:
    """Compute eval card status from aggregated test invocation data."""
    if has_passed:
        return "passed"
    if completed_invocations > 0 or total_invocations > 0:
        return "in-progress"
    return "not-started"
