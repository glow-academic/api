"""End-to-end tests for implemented attempt HTTP routes."""

from __future__ import annotations

import base64
import io
import zipfile
from uuid import UUID

import pytest


async def _create_attempt_route_graph(pool, actor, redis_client=None):
    from app.infra.globals import UPLOAD_FOLDER
    from app.tools.entries.attempt.create import create_attempt
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_archive.search import (
        search_attempt_archives,
    )
    from app.tools.entries.attempt_chat.create import create_attempt_chat
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_bridge.create import (
        create_attempt_chat_bridge,
    )
    from app.tools.entries.attempt_chat_bridge.refresh import (
        refresh_attempt_chat_bridge,
    )
    from app.tools.entries.attempt_home.create import create_attempt_home
    from app.tools.entries.attempt_message.create import (
        create_attempt_message,
    )
    from app.tools.entries.attempt_message.refresh import (
        refresh_attempt_message,
    )
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.home.create import create_home
    from app.tools.entries.home_chat.create import create_home_chat
    from app.tools.entries.messages.create import create_message
    from app.tools.entries.persona.create import create_persona
    from app.tools.entries.runs.create import create_run
    from app.tools.resources.options.create import create_option
    from app.tools.resources.questions.create import create_question

    async with pool.acquire() as conn:
        group = await create_group(
            conn, session_id=actor.session_id, name="attempt-route"
        )
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=actor.session_id,
            profiles_id=actor.profiles_id,
        )
        call = await create_call(conn, run_id=run.id, session_id=actor.session_id)
        user_persona = await create_persona(conn)
        attempt = await create_attempt(
            conn,
            call_id=call.id,
            user_persona_id=user_persona.id,
            profiles_id=actor.profiles_id,
            name="Route Attempt",
            description="Route attempt description",
        )
        chat = await create_chat(conn, session_id=actor.session_id)
        chat_call = await create_call(conn, run_id=run.id, session_id=actor.session_id)
        attempt_chat = await create_attempt_chat(
            conn,
            call_id=chat_call.id,
            group_id=group.id,
            chat_id=chat.id,
            title="Route Chat",
            position=0,
            text_enabled=True,
        )
        await create_attempt_chat_bridge(
            conn,
            attempt_id=attempt.id,
            attempt_chat_id=attempt_chat.id,
            session_id=actor.session_id,
        )
        home = await create_home(
            conn,
            session_id=actor.session_id,
            cohorts_ids=[],
            departments_ids=[actor.department_id],
            simulations_ids=[],
            profiles_ids=[actor.profiles_id],
            profile_personas_ids=[],
            simulation_availability_ids=[],
            simulation_positions_ids=[],
        )
        await create_home_chat(
            conn,
            home_id=home.id,
            chat_id=chat.id,
            session_id=actor.session_id,
        )
        await create_attempt_home(
            conn,
            attempt_id=attempt.id,
            home_id=home.id,
            session_id=actor.session_id,
        )
        message = await create_message(conn, run_id=run.id, role="user")
        message_call = await create_call(
            conn, run_id=run.id, session_id=actor.session_id
        )
        await create_attempt_message(
            conn,
            chat_id=attempt_chat.id,
            message_id=message.id,
            call_id=message_call.id,
        )
        question = None
        option = None
        if redis_client is not None:
            question = await create_question(
                conn,
                "Route question",
                30,
                redis_client,
            )
            option = await create_option(
                conn,
                "Route option",
                redis_client,
                question_id=question.id,
            )
        await refresh_attempt_chat_bridge(conn)
        await refresh_attempt_chat(conn)
        await refresh_attempt_message(conn)
        await refresh_attempt(conn)

    return {
        "attempt_id": str(attempt.id),
        "attempt_chat_id": str(attempt_chat.id),
        "message_id": str(message.id),
        "question_id": str(question.id) if question else None,
        "option_id": str(option.id) if option else None,
        "upload_folder": UPLOAD_FOLDER,
        "search_attempt_archives": search_attempt_archives,
    }


async def _create_attempt_start_home(pool, redis_client, actor) -> dict[str, str]:
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.chat.refresh import refresh_chat
    from app.tools.entries.home.create import create_home
    from app.tools.entries.home.refresh import refresh_home
    from app.tools.entries.home_chat.create import create_home_chat
    from app.tools.entries.home_chat.refresh import refresh_home_chat
    from app.tools.resources.personas.create import create_persona
    from app.tools.resources.profile_personas.create import (
        create_profile_persona,
    )

    async with pool.acquire() as conn:
        persona = await create_persona(
            conn,
            redis_client,
            department_ids=[actor.department_id],
        )
        profile_persona = await create_profile_persona(
            conn,
            profile_id=actor.profiles_id,
            persona_id=persona.id,
            redis=redis_client,
        )
        home = await create_home(
            conn,
            session_id=actor.session_id,
            cohorts_ids=[],
            departments_ids=[actor.department_id],
            simulations_ids=[],
            profiles_ids=[actor.profiles_id],
            profile_personas_ids=[profile_persona.id],
            simulation_availability_ids=[],
            simulation_positions_ids=[],
        )
        chat = await create_chat(
            conn,
            session_id=actor.session_id,
            department_ids=[actor.department_id],
            text_enabled=True,
        )
        await create_home_chat(
            conn,
            home_id=home.id,
            chat_id=chat.id,
            session_id=actor.session_id,
        )
        await refresh_chat(conn)
        await refresh_home_chat(conn)
        await refresh_home(conn)

    return {"home_id": str(home.id), "chat_id": str(chat.id)}


@pytest.mark.asyncio
class TestAttemptRoute:
    async def test_start_attempt_route_creates_attempt_via_real_stack(
        self,
        pool,
        redis_client,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_start_home(
            pool, redis_client, attempt_route_actor
        )
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/start",
            json={"home_id": graph["home_id"], "infinite_mode": False},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["attempt_id"]

        async with pool.acquire() as conn:
            stored_attempt_id = await conn.fetchval(
                "SELECT id FROM attempt_entry WHERE id = $1",
                UUID(payload["attempt_id"]),
            )

        assert stored_attempt_id == UUID(payload["attempt_id"])

    async def test_next_attempt_route_uses_real_http_stack(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/next",
            json={"attempt_id": graph["attempt_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["attempt_id"] == graph["attempt_id"]
        assert "chat_id" in payload

    async def test_get_attempt_route_returns_attempt_bundle(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/get",
            json={"attempt_id": graph["attempt_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "attempt"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["attempt_exists"] is True
        assert payload["access_denied"] is False
        assert payload["attempt"]["id"] == graph["attempt_id"]
        assert payload["entries"]["attempt_chat"]
        assert payload["entries"]["attempt_message"]
        assert payload["current_chat_id"] == graph["attempt_chat_id"]
        assert payload["has_messages"] is True

    async def test_attempt_docs_route_returns_composed_docs(
        self,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "attempt"
        assert payload["type"] == "analytics"
        assert payload["entries"]
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {"attempt_get", "archive_attempts", "export_attempt"} <= op_names

    async def test_attempt_export_route_creates_zip_upload(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/export",
            json={"attempt_id": graph["attempt_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["file_name"].endswith(".zip")
        assert payload["row_count"] >= 1
        assert payload["mime_type"] == "application/zip"

        archive_bytes = base64.b64decode(payload["content"])
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            assert sorted(archive.namelist()) == [
                "attempts.csv",
                "chats.csv",
                "messages.csv",
            ]

    async def test_attempt_refresh_route_returns_invalidated_tags(
        self,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "attempt,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["attempt_mv"]
        assert payload["invalidated_tags"] == ["attempt", "artifacts"]

    async def test_attempt_archive_route_creates_archive_entries(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/archive",
            json={
                "archived": True,
                "attempt_ids": [graph["attempt_id"]],
            },
        )

        assert response.status_code == 200, response.text
        assert "attempts" in response.headers["X-Invalidate-Tags"]
        payload = response.json()
        assert payload["updated_count"] == 1

        async with pool.acquire() as conn:
            archives = await graph["search_attempt_archives"](
                conn,
                attempt_ids=[UUID(graph["attempt_id"])],
                bypass_mv=True,
            )

        assert archives

    async def test_attempt_end_route_creates_grade_via_real_http_stack(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/end",
            json={
                "attempt_id": graph["attempt_id"],
                "chat_id": graph["attempt_chat_id"],
                "grade": True,
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat_id"] == graph["attempt_chat_id"]
        assert payload["grade_id"]

        async with pool.acquire() as conn:
            stored_grade_id = await conn.fetchval(
                "SELECT id FROM attempt_grade_entry WHERE id = $1",
                UUID(payload["grade_id"]),
            )

        assert stored_grade_id == UUID(payload["grade_id"])

    async def test_attempt_grade_route_creates_grade_via_real_http_stack(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/grade",
            json={
                "attempt_id": graph["attempt_id"],
                "chat_id": graph["attempt_chat_id"],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat_id"] == graph["attempt_chat_id"]
        assert payload["grade_id"]

        async with pool.acquire() as conn:
            stored_grade_id = await conn.fetchval(
                "SELECT id FROM attempt_grade_entry WHERE id = $1",
                UUID(payload["grade_id"]),
            )

        assert stored_grade_id == UUID(payload["grade_id"])

    async def test_attempt_message_route_persists_user_message_via_real_http_stack(
        self,
        pool,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        from app.tools.entries.attempt_message.search import (
            search_attempt_messages,
        )

        graph = await _create_attempt_route_graph(pool, attempt_route_actor)
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/message",
            json={
                "attempt_id": graph["attempt_id"],
                "chat_id": graph["attempt_chat_id"],
                "message": "Route test message",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat_id"] == graph["attempt_chat_id"]
        assert payload["user_message_id"]

        async with pool.acquire() as conn:
            messages, _ = await search_attempt_messages(
                conn,
                chat_ids=[UUID(graph["attempt_chat_id"])],
                bypass_mv=True,
                limit=1000,
            )

        message_ids = {str(item.message_id) for item in messages}
        assert payload["user_message_id"] in message_ids

    async def test_attempt_response_route_persists_response_via_real_http_stack(
        self,
        pool,
        redis_client,
        v5_attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(
            pool, attempt_route_actor, redis_client=redis_client
        )
        v5_attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await v5_attempt_route_client.client.post(
            "/v5/attempt/response",
            json={
                "chat_id": graph["attempt_chat_id"],
                "question_id": graph["question_id"],
                "option_ids": [graph["option_id"]],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["message"] == "Response submitted"
        assert payload["is_correct"] is None
        assert payload["response_id"]

        async with pool.acquire() as conn:
            stored_response_id = await conn.fetchval(
                "SELECT id FROM attempt_responses_entry WHERE id = $1",
                UUID(payload["response_id"]),
            )

        assert stored_response_id == UUID(payload["response_id"])
