"""Resolve contested tool results across agents using per-tool-call scoring.

Pure functions — no I/O, no Redis, no DB.  Unit-testable in isolation.

Algorithm:
  1. Group scored tool results by tool_name per agent.
  2. Within each tool_name group, pair results by position (call order).
  3. For each pair, apply the resolution strategy to pick a winner.
  4. Unmatched extras (one agent produced more calls) are auto-promoted.
  5. Return promote/fail result_id lists.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScoredToolResult:
    """A single tool call result with its eval score."""

    agent_id: str
    tool_name: str
    result_id: str
    score: float


@dataclass(frozen=True)
class ResolutionOutcome:
    """Which result_ids to promote vs fail."""

    promote: list[str]
    fail: list[str]


def resolve_tool_results(
    results: list[ScoredToolResult],
    *,
    strategy: str = "max",
    threshold: float | None = None,
) -> ResolutionOutcome:
    """Resolve contested tool results across agents.

    Groups by tool_name, pairs by position (insertion order per agent),
    applies strategy per pair, auto-promotes unmatched extras.

    Strategies:
      max       — highest score wins per pair
      threshold — highest score wins, but reject both if winner < threshold
      consensus — random if gap < threshold, otherwise highest wins
      random    — coin flip per pair (ignores scores)
    """
    # 1. Group by tool_name → agent_id → ordered list of results
    groups: dict[str, dict[str, list[ScoredToolResult]]] = {}
    for r in results:
        groups.setdefault(r.tool_name, {}).setdefault(r.agent_id, []).append(r)

    promote: list[str] = []
    fail: list[str] = []

    # 2. For each tool_name, pair by position across agents
    for _tool_name, agent_results in groups.items():
        agents = list(agent_results.keys())

        if len(agents) == 1:
            # Uncontested — single agent, promote all
            for r in agent_results[agents[0]]:
                promote.append(r.result_id)
            continue

        # Get ordered lists per agent
        agent_lists = [agent_results[a] for a in agents]
        max_len = max(len(lst) for lst in agent_lists)

        for pos in range(max_len):
            # Collect candidates at this position
            candidates = []
            for lst in agent_lists:
                if pos < len(lst):
                    candidates.append(lst[pos])

            if len(candidates) == 1:
                # Unmatched extra — auto-promote (lossless)
                promote.append(candidates[0].result_id)
                continue

            # Apply strategy to pick winner(s) from candidates
            winners, losers = _apply_strategy(
                candidates, strategy=strategy, threshold=threshold
            )
            promote.extend(w.result_id for w in winners)
            fail.extend(l.result_id for l in losers)

    return ResolutionOutcome(promote=promote, fail=fail)


def _apply_strategy(
    candidates: list[ScoredToolResult],
    *,
    strategy: str,
    threshold: float | None,
) -> tuple[list[ScoredToolResult], list[ScoredToolResult]]:
    """Apply resolution strategy to a set of candidates at one position.

    Returns (winners, losers).
    """
    if strategy == "max":
        return _strategy_max(candidates)
    elif strategy == "threshold":
        return _strategy_threshold(candidates, threshold=threshold or 0.0)
    elif strategy == "consensus":
        return _strategy_consensus(candidates, margin=threshold or 0.0)
    elif strategy == "random":
        return _strategy_random(candidates)
    else:
        # Unknown strategy — fall back to max
        return _strategy_max(candidates)


def _strategy_max(
    candidates: list[ScoredToolResult],
) -> tuple[list[ScoredToolResult], list[ScoredToolResult]]:
    """Highest score wins."""
    best = max(candidates, key=lambda c: c.score)
    winners = [best]
    losers = [c for c in candidates if c is not best]
    return winners, losers


def _strategy_threshold(
    candidates: list[ScoredToolResult],
    *,
    threshold: float,
) -> tuple[list[ScoredToolResult], list[ScoredToolResult]]:
    """Highest score wins, but reject all if winner is below threshold."""
    best = max(candidates, key=lambda c: c.score)
    if best.score < threshold:
        # All fail — none meet the bar
        return [], list(candidates)
    winners = [best]
    losers = [c for c in candidates if c is not best]
    return winners, losers


def _strategy_consensus(
    candidates: list[ScoredToolResult],
    *,
    margin: float,
) -> tuple[list[ScoredToolResult], list[ScoredToolResult]]:
    """If gap between top two < margin, random. Otherwise highest wins."""
    sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
    top = sorted_candidates[0]
    second = sorted_candidates[1]

    if top.score - second.score < margin:
        # Too close to call — pick randomly
        return _strategy_random(candidates)
    else:
        winners = [top]
        losers = [c for c in candidates if c is not top]
        return winners, losers


def _strategy_random(
    candidates: list[ScoredToolResult],
) -> tuple[list[ScoredToolResult], list[ScoredToolResult]]:
    """Random pick, ignoring scores."""
    winner = _random.choice(candidates)
    losers = [c for c in candidates if c is not winner]
    return [winner], losers
