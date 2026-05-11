from app.infra.leaderboard.get import _resolve_attempt_type_filter


def test_attempt_type_filter_returns_general_for_general_only() -> None:
    assert _resolve_attempt_type_filter(["general"]) == "general"


def test_attempt_type_filter_returns_practice_for_practice_only() -> None:
    assert _resolve_attempt_type_filter(["practice"]) == "practice"


def test_attempt_type_filter_returns_all_for_both_or_neither() -> None:
    assert _resolve_attempt_type_filter(["general", "practice"]) is None
    assert _resolve_attempt_type_filter([]) is None
    assert _resolve_attempt_type_filter(None) is None
    assert _resolve_attempt_type_filter(["archived"]) is None
