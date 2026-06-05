"""Guard tests for the atomic seed orchestrator's setup decision.

``database.init.run`` builds a staging DB and then does a whole-DB
``ALTER DATABASE … RENAME`` swap over the target. That swap is
destructive: it discards whatever was previously live in the target DB.
A live ``university`` academic-demo instance (28 seeded attempts + all
academic data) was silently wiped when a re-seed ran with the default
``SEED_SETUP=fresh`` — ``fresh`` built cleanly and the swap replaced the
``university`` DB with a ``fresh`` one.

``_seed_decision`` is the pure (no-I/O) core of that guard. We test it
in isolation with the marker-set passed in as a parameter (deps as
params — no DB, no env).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# `database` is a top-level package at the repo root (sibling of `core`),
# which is not on the path under the `PYTHONPATH=core` test invocation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from database.init import _seed_decision  # noqa: E402


def _decide(setup: str, existing: list[str], *, force: bool = False):
    return _seed_decision(setup, existing, force=force, target_db="glowapi")


def test_first_seed_proceeds_when_no_markers():
    action, _ = _decide("university", [])
    assert action == "proceed"


def test_same_setup_is_idempotent_skip():
    action, message = _decide("university", ["university"])
    assert action == "skip"
    assert "already seeded for 'university'" in message


def test_refuses_to_downgrade_university_to_fresh():
    # The exact bug: a re-seed defaulting to `fresh` over a live
    # `university` DB must NOT silently discard the academic data.
    action, message = _decide("fresh", ["university"])
    assert action == "refuse"
    assert "REFUSING" in message
    assert "university" in message
    assert "SEED_FORCE=1" in message


def test_refuses_any_different_setup_swap():
    action, _ = _decide("organization", ["university"])
    assert action == "refuse"


def test_force_overrides_downgrade_refusal():
    action, _ = _decide("fresh", ["university"], force=True)
    assert action == "proceed"


def test_force_overrides_idempotency_skip_for_reseed():
    # An intentional same-setup re-seed is allowed only under SEED_FORCE.
    action, _ = _decide("university", ["university"], force=True)
    assert action == "proceed"


def test_multiple_existing_setups_listed_in_refusal():
    action, message = _decide("fresh", ["organization", "university"])
    assert action == "refuse"
    assert "organization" in message
    assert "university" in message


@pytest.mark.parametrize("existing", [[], ["fresh"]])
def test_target_setup_present_or_absent_governs_skip(existing):
    action, _ = _decide("fresh", existing)
    assert action == ("skip" if "fresh" in existing else "proceed")
