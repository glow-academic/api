"""Invariant: every LLM-generation entry point enforces the request_limit.

RL-A (report-17) caught that #379 wired ``enforce_request_limit`` into only
attempt/test/system generate, leaving ``agent/generate`` — and, it turned out,
13 more ``*/generate.py`` impls — as unmetered LLM-cost bypasses. The
route-derived OWNERSHIP guardrail can't see a non-ownership class-fix like
rate-limiting, so the missed siblings slipped.

This is the durable fix: a structural invariant asserting EVERY
``core/app/infra/<artifact>/generate.py`` impl (each calls ``prepare_generation``
— the provider/LLM-cost path) references ``enforce_request_limit``. A new
generation artifact (or a fix that forgets one) fails this test instead of
shipping an unmetered endpoint.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_INFRA = Path(__file__).resolve().parents[2] / "app" / "infra"

# Artifacts whose generate.py is intentionally NOT an LLM-cost user endpoint.
# Empty today — every generate.py is a real generation path. Add here ONLY with
# a written reason if a future generate.py is genuinely not provider-cost.
_EXEMPT: dict[str, str] = {}


def _generate_impls() -> list[Path]:
    return sorted(_INFRA.glob("*/generate.py"))


def test_there_are_generate_impls():
    # Anti-vacuity: the glob must actually find the generation entry points.
    assert len(_generate_impls()) >= 15


@pytest.mark.parametrize(
    "path", _generate_impls(), ids=lambda p: p.parent.name
)
def test_generate_impl_enforces_request_limit(path: Path):
    artifact = path.parent.name
    src = path.read_text()
    tree = ast.parse(src)

    calls_prepare = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "prepare_generation"
        for n in ast.walk(tree)
    )
    calls_enforce = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "enforce_request_limit"
        for n in ast.walk(tree)
    )

    if artifact in _EXEMPT:
        pytest.skip(f"{artifact} exempt: {_EXEMPT[artifact]}")

    # Sanity: these really are LLM-cost generation paths.
    assert calls_prepare, f"{artifact}/generate.py no longer calls prepare_generation — re-check this guardrail"
    assert calls_enforce, (
        f"{artifact}/generate.py calls prepare_generation (LLM cost) but NOT "
        f"enforce_request_limit — every generation entry point must meter the "
        f"per-profile request_limit (RL-A). Add the enforce_request_limit block "
        f"after the permission check, or add an explicit _EXEMPT reason."
    )
