"""Return one item chosen with probability proportional to its weight."""

import random
from typing import TypeVar

T = TypeVar("T")


def weighted_choice(weighted_items: list[tuple[T, float]]) -> T | None:
    """Return one item chosen with probability proportional to its weight.

    Returns None when all weights are non-positive or list is empty.
    """
    if not weighted_items:
        return None
    # Ensure non-negative weights
    weights = [max(0.0, float(w)) for _, w in weighted_items]
    total = sum(weights)
    if total <= 0.0:
        return None
    r = random.random() * total
    cumsum = 0.0
    for item, w in weighted_items:
        cumsum += max(0.0, float(w))
        if r <= cumsum:
            return item
    return weighted_items[-1][0]
