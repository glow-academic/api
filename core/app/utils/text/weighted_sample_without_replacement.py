"""Sample up to k unique items proportionally to scores without replacement."""

import random
from typing import Any


def weighted_sample_without_replacement(
    items: list[Any], scores: list[float], k: int
) -> list[Any]:
    """Sample up to k unique items proportionally to scores without replacement.

    Falls back to fewer items if necessary.
    """
    selected: list[Any] = []
    pool_items = list(items)
    pool_scores = [max(0.0, float(s)) for s in scores]
    for _ in range(min(k, len(pool_items))):
        total = sum(pool_scores)
        if total <= 0.0:
            # pick uniformly at random from remaining
            choice_idx = random.randrange(len(pool_items))
        else:
            r = random.random() * total
            cumsum = 0.0
            choice_idx = 0
            for i, s in enumerate(pool_scores):
                cumsum += s
                if r <= cumsum:
                    choice_idx = i
                    break
        selected.append(pool_items.pop(choice_idx))
        pool_scores.pop(choice_idx)
    return selected
