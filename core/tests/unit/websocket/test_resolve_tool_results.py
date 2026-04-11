"""Tests for per-tool-call resolution logic."""

from app.infra.websocket.resolve_tool_results import (
    ResolutionOutcome,
    ScoredToolResult,
    resolve_tool_results,
)


def _r(agent_id: str, tool_name: str, result_id: str, score: float) -> ScoredToolResult:
    return ScoredToolResult(
        agent_id=agent_id,
        tool_name=tool_name,
        result_id=result_id,
        score=score,
    )


# ---------------------------------------------------------------------------
# max strategy
# ---------------------------------------------------------------------------


def test_max_single_tool_two_agents():
    """Basic 1v1 — higher score wins."""
    results = [
        _r("a", "create_name", "r1", 6),
        _r("b", "create_name", "r2", 8),
    ]
    out = resolve_tool_results(results, strategy="max")
    assert "r2" in out.promote
    assert "r1" in out.fail


def test_max_multiple_positions():
    """Two agents, 2 calls each — paired by position."""
    results = [
        _r("a", "create_item", "a1", 7),
        _r("a", "create_item", "a2", 5),
        _r("b", "create_item", "b1", 9),
        _r("b", "create_item", "b2", 4),
    ]
    out = resolve_tool_results(results, strategy="max")
    # pos 0: a1=7 vs b1=9 → b1 wins
    assert "b1" in out.promote
    assert "a1" in out.fail
    # pos 1: a2=5 vs b2=4 → a2 wins
    assert "a2" in out.promote
    assert "b2" in out.fail


def test_max_lossless_extras():
    """Agent A has 3 items, Agent B has 2 — extra auto-promoted."""
    results = [
        _r("a", "create_item", "a1", 7),
        _r("a", "create_item", "a2", 5),
        _r("a", "create_item", "a3", 8),
        _r("b", "create_item", "b1", 9),
        _r("b", "create_item", "b2", 4),
    ]
    out = resolve_tool_results(results, strategy="max")
    # pos 0: b1 wins
    assert "b1" in out.promote
    assert "a1" in out.fail
    # pos 1: a2 wins
    assert "a2" in out.promote
    assert "b2" in out.fail
    # pos 2: a3 unmatched — auto-promote
    assert "a3" in out.promote
    assert "a3" not in out.fail


def test_max_multiple_tool_types():
    """Different tool types resolved independently."""
    results = [
        _r("a", "create_item", "a_item", 5),
        _r("b", "create_item", "b_item", 9),
        _r("a", "create_name", "a_name", 8),
        _r("b", "create_name", "b_name", 6),
    ]
    out = resolve_tool_results(results, strategy="max")
    # items: b wins
    assert "b_item" in out.promote
    assert "a_item" in out.fail
    # names: a wins
    assert "a_name" in out.promote
    assert "b_name" in out.fail


def test_max_uncontested_single_agent():
    """Only one agent produced results for a tool — all promoted."""
    results = [
        _r("a", "create_name", "r1", 7),
        _r("a", "create_name", "r2", 5),
    ]
    out = resolve_tool_results(results, strategy="max")
    assert "r1" in out.promote
    assert "r2" in out.promote
    assert out.fail == []


# ---------------------------------------------------------------------------
# threshold strategy
# ---------------------------------------------------------------------------


def test_threshold_winner_above():
    """Winner above threshold — promoted."""
    results = [
        _r("a", "create_name", "r1", 3),
        _r("b", "create_name", "r2", 8),
    ]
    out = resolve_tool_results(results, strategy="threshold", threshold=5)
    assert "r2" in out.promote
    assert "r1" in out.fail


def test_threshold_both_below():
    """Both below threshold — both fail."""
    results = [
        _r("a", "create_name", "r1", 3),
        _r("b", "create_name", "r2", 4),
    ]
    out = resolve_tool_results(results, strategy="threshold", threshold=5)
    assert out.promote == []
    assert "r1" in out.fail
    assert "r2" in out.fail


def test_threshold_lossless_extra_not_gated():
    """Unmatched extra is auto-promoted regardless of threshold."""
    results = [
        _r("a", "create_item", "a1", 3),
        _r("a", "create_item", "a2", 2),
        _r("b", "create_item", "b1", 8),
    ]
    out = resolve_tool_results(results, strategy="threshold", threshold=5)
    # pos 0: b1=8 wins (above threshold)
    assert "b1" in out.promote
    assert "a1" in out.fail
    # pos 1: a2 unmatched — auto-promote (lossless, no threshold gate)
    assert "a2" in out.promote


# ---------------------------------------------------------------------------
# consensus strategy
# ---------------------------------------------------------------------------


def test_consensus_clear_gap():
    """Gap > margin — highest wins deterministically."""
    results = [
        _r("a", "create_name", "r1", 3),
        _r("b", "create_name", "r2", 8),
    ]
    out = resolve_tool_results(results, strategy="consensus", threshold=2.0)
    assert "r2" in out.promote
    assert "r1" in out.fail


def test_consensus_within_margin():
    """Gap < margin — one promoted, one failed (random pick)."""
    results = [
        _r("a", "create_name", "r1", 7),
        _r("b", "create_name", "r2", 7.5),
    ]
    out = resolve_tool_results(results, strategy="consensus", threshold=2.0)
    # One wins, one loses — we just don't know which
    assert len(out.promote) == 1
    assert len(out.fail) == 1
    assert set(out.promote + out.fail) == {"r1", "r2"}


# ---------------------------------------------------------------------------
# random strategy
# ---------------------------------------------------------------------------


def test_random_always_one_winner():
    """Random — one promoted, one failed, scores ignored."""
    results = [
        _r("a", "create_name", "r1", 1),
        _r("b", "create_name", "r2", 10),
    ]
    out = resolve_tool_results(results, strategy="random")
    assert len(out.promote) == 1
    assert len(out.fail) == 1
    assert set(out.promote + out.fail) == {"r1", "r2"}


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


def test_empty_results():
    """No results — nothing to promote or fail."""
    out = resolve_tool_results([], strategy="max")
    assert out.promote == []
    assert out.fail == []


def test_three_agents():
    """Three agents contest one position — one winner, two losers."""
    results = [
        _r("a", "create_name", "r1", 5),
        _r("b", "create_name", "r2", 9),
        _r("c", "create_name", "r3", 7),
    ]
    out = resolve_tool_results(results, strategy="max")
    assert out.promote == ["r2"]
    assert set(out.fail) == {"r1", "r3"}


def test_full_scenario():
    """Full scenario from design doc: 2 agents, mixed tools, lossless."""
    results = [
        _r("a", "create_item", "a1", 7),
        _r("a", "create_item", "a2", 5),
        _r("a", "create_item", "a3", 8),
        _r("b", "create_item", "b1", 9),
        _r("b", "create_item", "b2", 4),
        _r("a", "create_name", "a_name", 6),
        _r("b", "create_name", "b_name", 7),
    ]
    out = resolve_tool_results(results, strategy="max")
    # items: b1 wins pos0, a2 wins pos1, a3 auto-promote
    assert "b1" in out.promote
    assert "a2" in out.promote
    assert "a3" in out.promote
    assert "a1" in out.fail
    assert "b2" in out.fail
    # names: b_name wins
    assert "b_name" in out.promote
    assert "a_name" in out.fail
    # totals
    assert len(out.promote) == 4
    assert len(out.fail) == 3
