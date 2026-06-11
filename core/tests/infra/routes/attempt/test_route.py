"""End-to-end tests for implemented attempt HTTP routes.

The attempt flow endpoints were restructured into the ``chat_*`` /
``complete`` namespace (commits 6684bb99f5 ``remove proceed/next``,
91f475a2f2 ``introduce attempt_complete primitive, remove end/end_all``,
2ae3eee978 ``restructure attempt routes into attempt/chat/`` namespace).
These tests now exercise the current interface; the intent of each
migrated case is preserved in its docstring.

Old → new endpoint mapping applied here:

* ``POST /attempt/next``     → ``POST /attempt/chat_create`` (bridge an
  attempt_chat into the attempt; returns ``attempt_chat_id``)
* ``POST /attempt/end``      → ``POST /attempt/complete`` (mark the whole
  attempt complete; returns ``completion_id``)
* ``POST /attempt/grade``    → ``POST /attempt/chat_grade`` (record a
  manual grade for an attempt chat; returns ``grade_id``)
* ``POST /attempt/message``  → ``POST /attempt/chat_message`` (persist a
  user message; returns ``message_id``)
* ``POST /attempt/response`` → ``POST /attempt/chat_response`` (submit a
  question response; returns ``response_id``)

Test data is built through the shared black-box factory
:func:`tests.helpers.create_attempt_chat_graph` (session → group → run →
call → persona → attempt → chat → attempt_chat → bridge) plus a few
extra black-box ``create_*`` tools — no raw SQL for data setup. Both the
db pool and redis flow in as the standard ``pool`` / ``redis_client``
fixtures.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from tests.helpers import create_attempt_chat_graph


async def _create_attempt_route_graph(pool, redis, actor):
    """Build a full attempt → chat → message graph via black-box tools.

    Uses the shared :func:`create_attempt_chat_graph` factory for the
    core chain, then adds an ``attempt_message`` (so ``/attempt/get``
    surfaces messages) on top. Returns the IDs the route tests assert on.
    """
    from app.infra.globals import UPLOAD_FOLDER
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_archive.search import search_attempt_archives
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_bridge.refresh import (
        refresh_attempt_chat_bridge,
    )
    from app.tools.entries.attempt_message.create import create_attempt_message
    from app.tools.entries.attempt_message.refresh import refresh_attempt_message

    async with pool.acquire() as conn:
        graph = await create_attempt_chat_graph(
            conn,
            redis,
            actor.profiles_id,
            title="Route Chat",
            position=0,
            text_enabled=True,
        )
        message = await create_attempt_message(
            conn,
            redis,
            chat_id=graph.attempt_chat_id,
            session_id=graph.session_id,
        )
        # Materialize the chain so the route handlers (which read the MVs
        # without bypass) can see the freshly-created rows.
        await refresh_attempt_chat_bridge(conn)
        await refresh_attempt_chat(conn)
        await refresh_attempt_message(conn)
        await refresh_attempt(conn)

    return {
        "session_id": str(graph.session_id),
        "attempt_id": str(graph.attempt_id),
        "chat_id": str(graph.chat_id),
        "attempt_chat_id": str(graph.attempt_chat_id),
        "persona_id": str(graph.persona_id),
        "message_id": str(message.id),
        "upload_folder": UPLOAD_FOLDER,
        "search_attempt_archives": search_attempt_archives,
    }


async def _create_response_question(pool, redis, actor):
    """Create a question + option resource for the response submission test."""
    from app.tools.resources.options.create import create_option
    from app.tools.resources.questions.create import create_question

    async with pool.acquire() as conn:
        question = await create_question(conn, "Route question", 30, redis)
        option = await create_option(
            conn, "Route option", redis, question_id=question.id
        )
    return str(question.id), str(option.id)


async def _create_attempt_start_home(pool, redis, actor) -> dict[str, str]:
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.home.create import create_home
    from app.tools.entries.home.refresh import refresh_home
    from app.tools.entries.home_chat.create import create_home_chat
    from app.tools.entries.home_chat.refresh import refresh_home_chat
    from app.tools.resources.personas.create import create_persona
    from app.tools.resources.profile_personas.create import create_profile_persona

    async with pool.acquire() as conn:
        persona = await create_persona(
            conn,
            redis,
            department_ids=[actor.department_id],
        )
        profile_persona = await create_profile_persona(
            conn,
            profile_id=actor.profiles_id,
            persona_id=persona.id,
            redis=redis,
        )
        home = await create_home(
            conn,
            redis,
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
            redis,
            session_id=actor.session_id,
            department_ids=[actor.department_id],
            text_enabled=True,
        )
        await create_home_chat(
            conn,
            redis,
            home_id=home.id,
            chat_id=chat.id,
            session_id=actor.session_id,
        )
        # NOTE: chat_mv is intentionally NOT refreshed here. `refresh_chat`
        # issues `REFRESH MATERIALIZED VIEW CONCURRENTLY chat_mv`, but
        # chat_mv has no unique index (unlike its siblings attempt_chat_mv
        # / home_chat_mv), so a concurrent refresh always raises. The
        # /attempt/start path resolves the chat through home_chat, so the
        # home + home_chat MVs are sufficient for this test.
        await refresh_home_chat(conn)
        await refresh_home(conn)

    return {"home_id": str(home.id), "chat_id": str(chat.id)}


@pytest.mark.asyncio
class TestAttemptRoute:
    async def test_start_attempt_route_creates_attempt_via_real_stack(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_start_home(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/start",
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

    async def test_chat_create_route_bridges_chat_into_attempt(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        """Migrated from the removed ``POST /attempt/next``.

        Intent: advance an existing attempt to another chat and get the
        chat id back. ``/attempt/chat_create`` with
        ``previous_attempt_chat_id`` bridges a not-yet-attached
        attempt_chat into the attempt — the current "next chat in this
        attempt" path — and returns its ``attempt_chat_id``. The
        ``previous_attempt_chat_id`` short-circuit skips resource setup,
        so it exercises the same bridge write the old ``/next`` did.
        """
        from app.tools.entries.attempt_chat.create import create_attempt_chat
        from app.tools.entries.chat.create import create_chat

        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )

        # A second, freshly-created attempt_chat that is NOT yet bridged
        # into the attempt — the "next" chat the caller advances to.
        async with pool.acquire() as conn:
            next_chat = await create_chat(
                conn, redis_client, session_id=UUID(graph["session_id"])
            )
            next_attempt_chat = await create_attempt_chat(
                conn,
                redis_client,
                session_id=UUID(graph["session_id"]),
                chat_id=next_chat.id,
                title="Next Chat",
                position=1,
                text_enabled=True,
            )

        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/chat_create",
            json={
                "attempt_id": graph["attempt_id"],
                "chat_id": graph["chat_id"],
                "previous_attempt_chat_id": str(next_attempt_chat.id),
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["attempt_chat_id"] == str(next_attempt_chat.id)

        # The bridge between the attempt and the advanced-to chat now exists.
        async with pool.acquire() as conn:
            bridged = await conn.fetchval(
                "SELECT 1 FROM attempt_chat_bridge_entry "
                "WHERE attempt_id = $1 AND attempt_chat_id = $2",
                UUID(graph["attempt_id"]),
                next_attempt_chat.id,
            )
        assert bridged == 1

    async def test_get_attempt_route_returns_attempt_bundle(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/get",
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

    async def test_attempt_export_route_creates_zip_upload(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/export",
            json={"attempt_id": graph["attempt_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        # Export now writes the artifact to the file store and returns a
        # download handle ({file_id, file_name, row_count}); the zip bytes
        # are fetched separately via /attempt/file/download.
        assert payload["file_id"]
        assert payload["file_name"].endswith(".zip")
        assert payload["row_count"] >= 1

    async def test_attempt_refresh_route_returns_invalidated_tags(
        self,
        attempt_route_client,
        attempt_route_actor,
    ):
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/refresh",
            json={},
        )

        # #331 (cache-tag fix): attempt complete/grade/refresh must also bust
        # the per-profile home/practice read-caches, which carry no
        # ``artifacts`` tag. ``refresh_attempt_impl`` appends
        # ``home:profile:{pid}`` / ``practice:profile:{pid}`` (pid = the acting
        # profile) on top of the static ``["attempt", "artifacts"]`` set.
        pid = str(attempt_route_actor.profile_id)
        expected_tags = [
            "attempt",
            "artifacts",
            f"home:profile:{pid}",
            f"practice:profile:{pid}",
        ]
        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == ",".join(expected_tags)
        payload = response.json()
        assert payload["success"] is True
        # refresh now enqueues the full attempt view set; attempt_mv is
        # always among the refreshed views.
        assert "attempt_mv" in payload["refreshed_views"]
        assert payload["invalidated_tags"] == expected_tags

    async def test_attempt_archive_route_creates_archive_entries(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/archive",
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
                redis_client,
                attempt_ids=[UUID(graph["attempt_id"])],
                bypass_mv=True,
            )

        assert archives

    async def test_attempt_complete_route_completes_attempt_via_real_http_stack(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        """Migrated from the removed ``POST /attempt/end``.

        Intent: ending an attempt persists a terminal record. The end
        endpoint was replaced by the ``attempt_complete`` primitive, which
        writes an ``attempt_completion_entry`` and returns its id.
        """
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/complete",
            json={"attempt_id": graph["attempt_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["attempt_id"] == graph["attempt_id"]
        assert payload["completion_id"]

        async with pool.acquire() as conn:
            stored_completion_id = await conn.fetchval(
                "SELECT id FROM attempt_completion_entry WHERE id = $1",
                UUID(payload["completion_id"]),
            )

        assert stored_completion_id == UUID(payload["completion_id"])

    async def test_attempt_chat_grade_route_creates_grade_via_real_http_stack(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        """Migrated from the removed ``POST /attempt/grade``.

        Intent: grading an attempt chat persists an
        ``attempt_grade_entry``. Now driven by ``/attempt/chat_grade``,
        which records a manual score for the chat.
        """
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/chat_grade",
            json={
                "chat_id": graph["attempt_chat_id"],
                "score": 1,
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

    async def test_attempt_chat_message_route_persists_user_message(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        """Migrated from the removed ``POST /attempt/message``.

        Intent: posting a user message persists it against the chat and
        the new message id is discoverable via the attempt_message search.
        Now driven by ``/attempt/chat_message``.
        """
        from app.tools.entries.attempt_message.search import (
            search_attempt_messages,
        )

        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/chat_message",
            json={
                "chat_id": graph["attempt_chat_id"],
                "text": "Route test message",
                "persona_id": graph["persona_id"],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["message_id"]

        async with pool.acquire() as conn:
            messages, _ = await search_attempt_messages(
                conn,
                redis_client,
                chat_ids=[UUID(graph["attempt_chat_id"])],
                bypass_mv=True,
                limit=1000,
            )

        message_ids = {str(item.message_id) for item in messages}
        assert payload["message_id"] in message_ids

    async def test_attempt_chat_response_route_persists_response(
        self,
        pool,
        redis_client,
        attempt_route_client,
        attempt_route_actor,
    ):
        """Migrated from the removed ``POST /attempt/response``.

        Intent: submitting a question response persists an
        ``attempt_responses_entry`` and reports success. Now driven by
        ``/attempt/chat_response``.
        """
        graph = await _create_attempt_route_graph(
            pool, redis_client, attempt_route_actor
        )
        question_id, option_id = await _create_response_question(
            pool, redis_client, attempt_route_actor
        )
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/chat_response",
            json={
                "chat_id": graph["attempt_chat_id"],
                "question_id": question_id,
                "option_ids": [option_id],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["response_id"]

        async with pool.acquire() as conn:
            stored_response_id = await conn.fetchval(
                "SELECT id FROM attempt_responses_entry WHERE id = $1",
                UUID(payload["response_id"]),
            )

        assert stored_response_id == UUID(payload["response_id"])
