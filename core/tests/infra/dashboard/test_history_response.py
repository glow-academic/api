from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.infra.types import ArtifactContext, ResourcePair
from app.routes.attempt.dashboard.search import _build_history_response
from app.tools.entries.attempt.types import GetAttemptResponse


def _ns(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def test_build_history_response_populates_filter_options_from_resources() -> None:
    attempt_id = uuid4()
    simulation_id = uuid4()
    profile_id = uuid4()
    scenario_id = uuid4()

    ctx = ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        entries={
            "attempts": [
                GetAttemptResponse(
                    attempt_id=attempt_id,
                    simulation_id=simulation_id,
                    profile_id=profile_id,
                    user_persona_id=None,
                    personas_id=None,
                    cohort_id=None,
                    department_id=None,
                    practice=False,
                    attempt_created_at=datetime(2026, 1, 1),
                    infinite_mode=False,
                    num_chats=0,
                    is_archived=False,
                    is_completed=True,
                    scenario_ids=[scenario_id],
                    chat_entry_id=None,
                    attempt_chat_id=None,
                )
            ],
            "attempt_chats": [],
            "total_count": 1,
        },
        resources={
            "simulations": ResourcePair(
                selected=[_ns(id=simulation_id, name="Simulation A")],
                suggestions=[],
            ),
            "scenarios": ResourcePair(
                selected=[_ns(id=scenario_id, name="Scenario A")],
                suggestions=[],
            ),
            "personas": ResourcePair(selected=[], suggestions=[]),
            "profiles": ResourcePair(
                selected=[_ns(id=profile_id, name="Learner A")],
                suggestions=[],
            ),
        },
    )

    response = _build_history_response(ctx)

    assert response.simulation_options
    assert response.simulation_options[0].value == str(simulation_id)
    assert response.scenario_options
    assert response.scenario_options[0].value == str(scenario_id)
    assert response.profile_options
    assert response.profile_options[0].value == str(profile_id)
