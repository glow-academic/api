from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.dashboard import context as dashboard_context
from app.infra.types import ArtifactContext, ResourcePair
from app.routes.attempt.dashboard.search import _build_history_response
from app.tools.entries.attempt.types import GetAttemptResponse
from tests.helpers import unique_tag


def _ns(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


class _Acquire:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


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


@pytest.mark.asyncio
async def test_dashboard_search_context_does_not_default_to_general_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_search_attempts(**kwargs: object) -> tuple[list[object], int]:
        calls.append(kwargs)
        return [], 0

    monkeypatch.setattr(dashboard_context, "search_attempts", fake_search_attempts)

    await dashboard_context.resolve_dashboard_search_context(
        _Pool(),  # type: ignore[arg-type]
        redis=None,  # type: ignore[arg-type]
        profile_resource_ids=[uuid4()],
    )

    assert calls[0]["practice"] is None
    assert calls[0]["is_archived"] is False


@pytest.mark.asyncio
async def test_dashboard_search_context_archived_filter_is_independent_of_practice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_search_attempts(**kwargs: object) -> tuple[list[object], int]:
        calls.append(kwargs)
        return [], 0

    monkeypatch.setattr(dashboard_context, "search_attempts", fake_search_attempts)

    await dashboard_context.resolve_dashboard_search_context(
        _Pool(),  # type: ignore[arg-type]
        redis=None,  # type: ignore[arg-type]
        profile_resource_ids=[uuid4()],
        show_archived=True,
    )

    assert calls[0]["practice"] is None
    assert calls[0]["is_archived"] is True


@pytest.mark.asyncio
async def test_dashboard_search_context_returns_general_and_practice_by_default(
    pool,
    redis_client,
) -> None:
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.sessions.create import create_session
    from app.tools.resources.profiles.create import create_profile

    async with pool.acquire() as conn:
        profile = await create_profile(
            conn,
            redis_client,
            name=f"dashboard-history-{unique_tag()}",
        )
        persona = await create_persona(conn)

        general_session = await create_session(conn, profile_id=profile.id)
        await create_group(
            conn, session_id=general_session.id, artifact_type="persona"
        )
        general_attempt = await create_attempt(
            conn,
            session_id=general_session.id,
            user_persona_id=persona.id,
            profiles_id=profile.id,
            practice=False,
        )

        practice_session = await create_session(conn, profile_id=profile.id)
        await create_group(
            conn, session_id=practice_session.id, artifact_type="persona"
        )
        practice_attempt = await create_attempt(
            conn,
            session_id=practice_session.id,
            user_persona_id=persona.id,
            profiles_id=profile.id,
            practice=True,
        )
        await refresh_attempt(conn)

    ctx = await dashboard_context.resolve_dashboard_search_context(
        pool,
        redis_client,
        profile_resource_ids=[profile.id],
        page_size=10,
    )

    attempt_ids = {item.attempt_id for item in ctx.entries["attempts"]}
    assert general_attempt.id in attempt_ids
    assert practice_attempt.id in attempt_ids
