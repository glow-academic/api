"""End-to-end tests for home, practice, and record HTTP routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def learning_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["home", "practice", "record", "dashboard"],
        group_name="learning-route",
        role_name_prefix="Learning Route Admin",
    )


async def _create_attempt_export_graph(pool, actor, *, practice: bool):
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.chat.refresh import refresh_chat
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.runs.create import create_run

    async with pool.acquire() as conn:
        group = await create_group(
            conn,
            session_id=actor.session_id,
            name=f"export-{'practice' if practice else 'home'}",
        )
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=actor.session_id,
            profiles_id=actor.profiles_id,
        )
        call = await create_call(
            conn,
            run_id=run.id,
            session_id=actor.session_id,
        )
        persona = await create_persona(conn)
        attempt = await create_attempt(
            conn,
            call_id=call.id,
            user_persona_id=persona.id,
            profiles_id=actor.profiles_id,
            practice=practice,
        )
        chat = await create_chat(
            conn,
            session_id=actor.session_id,
            department_ids=[actor.department_id],
            name=f"export-chat-{'practice' if practice else 'record'}",
            text_enabled=True,
        )
        await create_attempt_chat(
            conn,
            call_id=call.id,
            group_id=group.id,
            chat_id=chat.id,
            departments_ids=[actor.department_id],
            text_enabled=True,
        )
        await refresh_attempt(conn)
        await refresh_chat(conn)
        await refresh_attempt_chat(conn)

    return attempt.id


@pytest.mark.asyncio
class TestHomePracticeRecordRoutes:
    @staticmethod
    def _assert_tagged_for_artifact(response, artifact: str) -> None:
        tags = response.headers["X-Cache-Tags"].split(",")
        assert artifact in tags

    async def test_get_home_route_returns_bundle(
        self,
        v5_home_route_client,
        learning_route_actor,
    ):
        v5_home_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_home_route_client.client.post(
            "/v5/home/get",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "home")
        payload = response.json()
        assert payload["actor_name"] == learning_route_actor.name
        assert isinstance(payload["items"], list)
        assert payload["analytics"] is not None

    async def test_get_practice_route_returns_bundle(
        self,
        v5_practice_route_client,
        learning_route_actor,
    ):
        v5_practice_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_practice_route_client.client.post(
            "/v5/practice/get",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "practice")
        payload = response.json()
        assert payload["actor_name"] == learning_route_actor.name
        assert isinstance(payload["items"], list)
        assert payload["analytics"] is not None

    async def test_search_home_route_returns_history(
        self,
        v5_home_route_client,
        learning_route_actor,
    ):
        v5_home_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_home_route_client.client.post(
            "/v5/home/search",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "home")
        payload = response.json()
        assert isinstance(payload["data"], list)
        assert payload["page_size"] >= 0

    async def test_search_practice_route_returns_history(
        self,
        v5_practice_route_client,
        learning_route_actor,
    ):
        v5_practice_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_practice_route_client.client.post(
            "/v5/practice/search",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "practice")
        payload = response.json()
        assert isinstance(payload["data"], list)
        assert payload["page_size"] >= 0

    async def test_get_record_route_returns_dashboard_bundle(
        self,
        v5_record_route_client,
        learning_route_actor,
    ):
        v5_record_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_record_route_client.client.post(
            "/v5/record/get",
            json={"target_profile_id": str(learning_route_actor.profiles_id)},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "record")
        payload = response.json()
        assert payload["header_metrics"]
        assert payload["primary_metrics"]
        assert payload["secondary_metrics"]
        assert payload["history"]
        assert payload["simulation_options"] is not None

    async def test_export_home_route_creates_zip_upload(
        self,
        pool,
        v5_home_route_client,
        learning_route_actor,
    ):
        await _create_attempt_export_graph(
            pool,
            learning_route_actor,
            practice=False,
        )
        v5_home_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_home_route_client.client.post(
            "/v5/home/export"
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["row_count"] >= 1
        assert payload["file_name"].endswith(".zip")
        assert payload["content"]
        assert payload["mime_type"] == "application/zip"

    async def test_export_practice_route_creates_zip_upload(
        self,
        pool,
        v5_practice_route_client,
        learning_route_actor,
    ):
        await _create_attempt_export_graph(
            pool,
            learning_route_actor,
            practice=True,
        )
        v5_practice_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_practice_route_client.client.post(
            "/v5/practice/export"
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["row_count"] >= 1
        assert payload["file_name"].endswith(".zip")
        assert payload["content"]
        assert payload["mime_type"] == "application/zip"

    async def test_export_record_route_creates_zip_upload(
        self,
        pool,
        v5_record_route_client,
        learning_route_actor,
    ):
        await _create_attempt_export_graph(
            pool,
            learning_route_actor,
            practice=False,
        )
        v5_record_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await v5_record_route_client.client.post(
            "/v5/record/export",
            json={"target_profile_id": str(learning_route_actor.profiles_id)},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["row_count"] >= 1
        assert payload["file_name"].endswith(".zip")
        assert payload["content"]
        assert payload["mime_type"] == "application/zip"
