"""Shared test workflow logic, transport-agnostic apart from emitted payload shape."""

from __future__ import annotations
from app.infra.globals import get_redis_client

import uuid
from typing import Any

import asyncpg
from redis.asyncio import Redis

from app.infra.websocket.socket_event import EmitFn, client_event, internal_event
from app.infra.server_timing import timed


def _find_next_run_id(runs: list[Any], prev_run_id: str | None) -> str | None:
    """Return the next run's id after the one matching ``prev_run_id``.

    Used by ``test_group_impl`` to advance through a sorted list of runs in a
    test group. ``runs`` is whatever ``search_runs(...)`` returns — duck-typed
    on a ``.run_id`` attribute. ``prev_run_id`` is the previously-completed
    run's id (or ``None`` if we haven't started yet).

    Returns ``None`` when:
      - the list is empty,
      - ``prev_run_id`` doesn't match any run in the list,
      - or the matched run is the last one.

    When ``prev_run_id`` is ``None``, returns the first run's id.
    """
    if not runs:
        return None
    if prev_run_id is None:
        return runs[0].run_id
    for idx, run in enumerate(runs):
        if run.run_id == prev_run_id:
            if idx + 1 < len(runs):
                return runs[idx + 1].run_id
            return None
    return None


async def test_progress_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate test_progress_update to test_grade_start."""
    redis = get_redis_client()
    from app.infra.websocket.test_types import TestProgressData

    invocation_id = data.get("invocation_id") or data.get("chat_id")
    if not invocation_id:
        return

    sid = data.get("sid")
    invocation_id_str = str(invocation_id)
    rooms = [sid, f"test_{invocation_id_str}"] if sid else []

    await emit(
        [
            internal_event(
                "test.grade.started",
                TestProgressData(
                    sid=sid,
                    rooms=rooms,
                    invocation_id=invocation_id_str,
                    run_id=data.get("run_id"),
                    current_run=data.get("current_run"),
                    total_runs=data.get("total_runs"),
                    message=data.get("message"),
                ).model_dump(mode="json"),
            )
        ]
    )


async def test_run_done_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate test_run_done to test_run_complete."""
    redis = get_redis_client()
    from app.infra.websocket.test_types import TestRunCompleteData

    invocation_id = data.get("invocation_id") or data.get("chat_id")
    if not invocation_id:
        return

    invocation_id_str = str(invocation_id)
    current_run = data.get("current_run", 1)
    total_runs = data.get("total_runs", 1)
    remaining_runs = total_runs - current_run
    sid = data.get("sid")
    rooms = [sid, f"test_{invocation_id_str}"] if sid else []

    await emit(
        [
            internal_event(
                "test.run.completed",
                TestRunCompleteData(
                    sid=sid,
                    rooms=rooms,
                    invocation_id=invocation_id_str,
                    run_id=str(data.get("run_id")) if data.get("run_id") else None,
                    original_run_resource_id=str(data.get("original_run_resource_id"))
                    if data.get("original_run_resource_id")
                    else None,
                    tool_calls=data.get("tool_calls"),
                    current_run=current_run,
                    total_runs=total_runs,
                    remaining_runs=remaining_runs,
                ).model_dump(mode="json"),
            )
        ]
    )


async def test_error_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate test_error_event to test_error."""
    from app.infra.websocket.test_types import TestErrorData

    invocation_id = data.get("invocation_id") or data.get("chat_id")
    message = data.get("error_message") or data.get("message", "Test error")
    sid = data.get("sid")
    invocation_id_str = str(invocation_id) if invocation_id else None
    rooms = (
        [sid, f"test_{invocation_id_str}"]
        if sid and invocation_id_str
        else ([sid] if sid else [])
    )

    await emit(
        [
            internal_event(
                "test.end.error",
                TestErrorData(
                    sid=sid,
                    rooms=rooms,
                    invocation_id=invocation_id_str,
                    run_id=str(data.get("run_id")) if data.get("run_id") else None,
                    message=message,
                    error_type=data.get("error_type"),
                ).model_dump(mode="json"),
            )
        ]
    )


def _extract_grade_score(tool_results: list[dict[str, Any]]) -> int | None:
    for item in tool_results:
        result = item.get("result") or {}
        if not isinstance(result, dict):
            continue
        if isinstance(result.get("score"), int):
            return result["score"]
        if isinstance(result.get("total"), int):
            return result["total"]
    return None


def _extract_grade_passed(tool_results: list[dict[str, Any]]) -> bool | None:
    for item in tool_results:
        result = item.get("result") or {}
        if not isinstance(result, dict):
            continue
        if isinstance(result.get("passed"), bool):
            return result["passed"]
    return None


def _extract_grade_feedback(tool_results: list[dict[str, Any]]) -> str | None:
    for item in tool_results:
        result = item.get("result") or {}
        if not isinstance(result, dict):
            continue
        feedback = result.get("feedback")
        if isinstance(feedback, str) and feedback:
            return feedback
    return None


async def test_grade_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    profile_id: str,
) -> None:
    """Handle test grade completion and emit test_grade_progress."""
    redis = get_redis_client()
    from app.infra.websocket.test_types import TestGradedData
    from app.tools.entries.tokens.create import create_token
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)
    grade_id = data.get("grade_id")
    invocation_id = data.get("invocation_id") or data.get("chat_id")
    run_id = data.get("run_id")
    session_id = data.get("session_id")

    tool_results = data.get("tool_results") or []
    score = _extract_grade_score(tool_results)
    passed = _extract_grade_passed(tool_results)
    feedback = _extract_grade_feedback(tool_results)

    try:
        input_tokens = data.get("input_text_tokens", data.get("input_tokens", 0))
        output_tokens = data.get("output_text_tokens", data.get("output_tokens", 0))

        if run_id and session_id:
            async with pool.acquire() as conn:
                await create_token(
                    conn, redis,
                    run_id=uuid.UUID(run_id),
                    session_id=uuid.UUID(session_id),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        invocation_id_str = str(invocation_id) if invocation_id else ""
        rooms = (
            [data.get("sid"), f"test_{invocation_id_str}"]
            if invocation_id_str
            else [data.get("sid")]
        )

        await emit(
            [
                internal_event(
                    "test.grade.progress",
                    TestGradedData(
                        sid=data.get("sid"),
                        rooms=[r for r in rooms if r],
                        invocation_id=invocation_id_str,
                        grade_id=str(grade_id) if grade_id else None,
                        score=score,
                        passed=passed,
                        feedback=feedback,
                    ).model_dump(mode="json"),
                )
            ]
        )

        logger.info(
            f"Test grading complete - invocation_id={invocation_id}, "
            f"grade_id={grade_id}, score={score}, passed={passed}, profile_id={profile_id}"
        )
    except Exception as e:
        logger.exception(f"Failed to handle test grade completion: {e}")



async def test_group_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Orchestrate sequential runs within a group."""
    redis = get_redis_client()
    from app.infra.test.client_types import TestGroupPayload
    from app.infra.websocket.test_types import TestErrorData
    from app.tools.entries.runs.search import search_runs
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)
    sid = data.get("sid", "")

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        return

    try:
        payload = TestGroupPayload(**data)
    except Exception as e:
        logger.exception(f"Invalid test_group payload: {e}")
        return

    try:
        test_id = payload.test_id
        test_invocation_id = payload.test_invocation_id
        group_id_raw = data.get("group_id")
        if not group_id_raw:
            raise ValueError(f"Group not found for test {test_id}")
        group_id = uuid.UUID(str(group_id_raw))
        prev_run_id = payload.prev_run_id

        with timed("fetch_runs"):
          async with pool.acquire() as conn:
            runs, _ = await search_runs(
                conn, redis,
                group_ids=[group_id],
                sort_order="asc",
                limit=1000,
            )

        next_run_id = _find_next_run_id(runs, prev_run_id)
        if not next_run_id:
            await emit(
                [
                    internal_event(
                        "test.group.completed",
                        {
                            "sid": sid,
                            "test_id": str(test_id),
                            "test_invocation_id": str(test_invocation_id),
                            "group_id": str(group_id),
                        },
                    )
                ]
            )
            return

        await emit(
            [
                internal_event(
                    "test.run.triggered",
                    {
                        "sid": sid,
                        "profile_id": profile_id_str,
                        "session_id": data.get("session_id"),
                        "test_id": str(test_id),
                        "test_invocation_id": str(test_invocation_id),
                        "run_id": str(next_run_id),
                        "group_id": str(group_id),
                    },
                )
            ]
        )
    except Exception as e:
        logger.exception(f"Error in test_group: {e}")
        await emit(
            [
                internal_event(
                    "test.group.error",
                    TestErrorData(
                        sid=sid,
                        message=f"Failed to run group: {e}",
                        error_type="group",
                    ).model_dump(mode="json"),
                )
            ]
        )


async def test_next_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Find next invocation with pending runs and emit test_run or test_all_complete."""
    redis = get_redis_client()
    sid = data.get("sid", "")
    if not sid:
        return

    from app.infra.websocket.test_types import TestAllCompleteEvent
    from app.tools.entries.test_invocation.search import (
        search_test_invocation_entries_internal,
    )
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)

    try:
        test_id = uuid.UUID(str(data["test_id"]))
    except (KeyError, ValueError) as e:
        logger.exception(f"Invalid test_next data: {e}")
        await emit(
            [
                client_event(
                    "test.next.error",
                    {
                        "message": f"Failed to find next run: {e}",
                        "error_type": "internal",
                    },
                    room=sid,
                )
            ]
        )
        return

    try:
        with timed("fetch_runs"):
          async with pool.acquire() as conn:
            invocations, _total_count = await search_test_invocation_entries_internal(
                conn, redis,
                test_ids=[test_id],
                limit=1000,
            )
    except Exception as e:
        logger.exception(f"Error in test_next: {e}")
        await emit(
            [
                client_event(
                    "test.next.error",
                    {
                        "message": f"Failed to find next run: {e}",
                        "error_type": "internal",
                    },
                    room=sid,
                )
            ]
        )
        return

    if not invocations:
        logger.warning(f"No invocations found for test {test_id}")
        await emit(
            [
                client_event(
                    "test_all_complete",
                    TestAllCompleteEvent(
                        invocation_id="",
                        total_runs=0,
                        success=True,
                    ).model_dump(mode="json"),
                    room=sid,
                )
            ]
        )
        return

    for invocation in invocations:
        if not invocation.invocation_completed:
            if not invocation.group_id:
                await emit(
                    [
                        client_event(
                            "test.next.error",
                            {
                                "message": "Failed to find group for next test invocation",
                                "error_type": "internal",
                            },
                            room=sid,
                        )
                    ]
                )
                return
            # Drive the group orchestration directly. Previously this
            # emitted ``test.group.started`` which was subscribed by
            # ``ws/output/test/group/started.py`` → ``test_group_impl``.
            # That extra hop hid the workflow chain and swallowed any
            # exception inside the impl. Calling directly keeps the
            # orchestration in one async stack so failures propagate
            # back here and surface in the test_next_impl error path.
            await test_group_impl(
                {
                    "sid": sid,
                    "profile_id": data.get("profile_id"),
                    "session_id": data.get("session_id"),
                    "profiles_id": data.get("profiles_id"),
                    "test_invocation_id": str(invocation.invocation_id),
                    "test_id": str(test_id),
                    "group_id": str(invocation.group_id),
                },
                emit=emit,
                pool=pool,
            )
            return

    last_invocation = invocations[-1]
    total = len(invocations)
    await emit(
        [
            client_event(
                "test_all_complete",
                TestAllCompleteEvent(
                    invocation_id=str(last_invocation.invocation_id),
                    total_runs=total,
                    success=True,
                ).model_dump(mode="json"),
                room=sid,
            )
        ]
    )
    logger.info(f"All test runs complete - test_id={test_id}")


async def test_start_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
) -> None:
    """Create test via black boxes, optional benchmark bridge, delegate to test_proceed."""
    redis = get_redis_client()
    from app.infra.group.resolve import resolve_group_impl
    from app.infra.websocket.test_types import TestErrorData
    from app.tools.entries.benchmark_test.create import create_benchmark_test
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.sessions.create import create_session
    from app.infra.invocation.refresh import refresh_invocation_impl
    from app.infra.test.refresh import refresh_test_impl
    from app.tools.entries.test.create import create_test
    from app.utils.cache.invalidate_tags import invalidate_tags
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)
    sid = data.get("sid", "")

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        return

    try:
        profile_id = uuid.UUID(profile_id_str)
    except Exception as e:
        logger.exception(f"Invalid profile_id in test_start: {e}")
        return

    eval_id_raw = data.get("eval_id") or data.get("benchmark_id")
    eval_id = uuid.UUID(str(eval_id_raw)) if eval_id_raw else None
    infinite_mode = data.get("infinite_mode", False)
    # Soft/accept staging: create the test + junction dormant and stash a
    # pending soft_call keyed by the wrapper call_id (threaded in via data).
    soft = bool(data.get("soft", False))
    call_id_raw = data.get("call_id")
    soft_call_id = uuid.UUID(str(call_id_raw)) if call_id_raw else None
    profiles_id_str = data.get("profiles_id")
    if not profiles_id_str:
        logger.error("profiles_id missing from test_start payload")
        return

    session_id_str = data.get("session_id")

    try:
        profiles_id = uuid.UUID(profiles_id_str)

        if session_id_str:
            session_id = uuid.UUID(session_id_str)
        else:
            async with pool.acquire() as conn:
                session_id = (await create_session(conn, redis, profile_id=profiles_id)).id

        if redis is None:
            logger.error("test_start_impl requires redis for canonical group resolve")
            return

        with timed("group"):
            group_result = await resolve_group_impl(
                pool, redis,
                artifact_type="test",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = group_result.group_id

        with timed("db_write"):
         async with pool.acquire() as conn:
            # Resolve eval → parent benchmark + dynamic flag.
            benchmark_id: uuid.UUID | None = None
            is_dynamic = True
            if eval_id:
                from app.tools.entries.benchmark.search import search_benchmarks
                benchmarks = await search_benchmarks(
                    conn, redis, eval_ids=[eval_id], limit=1,
                )
                if not benchmarks:
                    raise ValueError(f"No benchmark found for eval {eval_id}")
                benchmark_id = benchmarks[0].benchmark_id
                is_dynamic = benchmarks[0].dynamic

            run_id = (
                await create_run(
                    conn, redis,
                    group_id=group_id,
                    session_id=session_id,
                )
            ).id
            call_id = (await create_call(conn, redis, run_id=run_id, session_id=session_id)).id
            result = await create_test(
                conn, redis,
                call_id=call_id,
                profiles_id=profiles_id,
                infinite_mode=infinite_mode,
                is_dynamic=is_dynamic,
                soft=soft,
            )
            test_id = result.id

            if benchmark_id is not None:
                await create_benchmark_test(
                    conn, redis,
                    benchmark_id=benchmark_id,
                    test_id=test_id,
                    session_id=session_id,
                    soft=soft,
                )

            # No pre-seeding of test_invocation_entry rows. Mirrors
            # attempt_start_impl: the test owns the wrapper; the client
            # calls /test/invocation/create per benchmark template card to
            # materialize a row when the user runs that card.

            generation_run_id = data.get("generation_run_id")
            if generation_run_id and redis:
                try:
                    await redis.setex(
                        f"generation_test_link:{test_id}",
                        3600,
                        generation_run_id,
                    )
                except Exception:
                    logger.warning(
                        f"Failed to store generation_test_link for test {test_id}"
                    )

        # Dormant (soft) rows won't surface in the MVs — defer refresh +
        # invalidation to the ack (accept) so a staged test costs nothing.
        if not soft:
            await refresh_test_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["test_mv"],
            )
            await refresh_invocation_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["test_invocation_mv"],
            )
            if redis:
                await invalidate_tags(["test", "tests", "benchmark"], redis=redis)

        # Client-orchestrated: mirrors attempt_start_impl, which returns
        # {attempt_id, chat_id} where chat_id is the FIRST chat_entry
        # template on the parent. We do the same: return {test_id,
        # invocation_id} where invocation_id is the first benchmark
        # invocation_entry (template). The client's useTestStart →
        # useTestRoute then fetches /test/invocation/get on that template
        # and either drops to lobby or fires /test/generate so the LLM
        # materializes a test_invocation_entry from it.
        first_invocation_id: str | None = None
        if benchmark_id is not None:
            async with pool.acquire() as conn:
                from app.tools.entries.invocation.search import (
                    search_invocations,
                )
                templates = await search_invocations(
                    conn, redis, benchmark_ids=[benchmark_id], limit=1,
                )
                if templates:
                    first_invocation_id = str(templates[0].id)

        # Soft: stash the staged test as a pending soft_call (keyed by the
        # server call_id) so the ack can activate test_entry + the junction.
        if soft and soft_call_id is not None:
            from app.tools.entries.soft_calls.create import create_soft_call
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=soft_call_id, artifact="test",
                    operation="start", artifact_id=test_id, status="pending",
                    patch={
                        "test_id": str(test_id),
                        "invocation_id": first_invocation_id,
                        "benchmark_id": str(benchmark_id) if benchmark_id else None,
                    },
                )

        data["_result"] = {
            "test_id": str(test_id),
            "invocation_id": first_invocation_id,
            "benchmark_id": str(benchmark_id) if benchmark_id else None,
        }

    except Exception as e:
        logger.exception(f"Error in test_start: {e}")
        await emit(
            [
                internal_event(
                    "test.start.error",
                    TestErrorData(
                        sid=sid,
                        message=f"Failed to start test: {e}",
                        error_type="start",
                    ).model_dump(mode="json"),
                )
            ]
        )





# ═══════════════════════════════════════════════════════════════════════════
# Test domain utilities (moved from app.socket.types)
# ═══════════════════════════════════════════════════════════════════════════




def build_messages_from_conversation(
    system_prompt: str | None,
    developer_instructions: list[str],
    original_conversation: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build messages array from original conversation.

    Auto-regressive replay pattern:
    1. Add system prompt
    2. Add developer instructions
    3. Add all messages EXCEPT remove tool_calls from last assistant message

    Args:
        system_prompt: System prompt from group config
        developer_instructions: Rendered developer instructions
        original_conversation: Original conversation from previous run

    Returns:
        Messages array ready for LLM completion
    """
    messages: list[dict[str, Any]] = []

    # Add system prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Add developer instructions
    for instruction in developer_instructions:
        messages.append({"role": "developer", "content": instruction})

    # Add original conversation with truncation
    if original_conversation:
        for i, msg in enumerate(original_conversation):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # For last assistant message, remove tool_calls to force regeneration
            is_last = i == len(original_conversation) - 1
            if is_last and role == "assistant":
                # Only include the content, not the tool_calls
                messages.append({"role": role, "content": content})
            else:
                # Include everything as-is
                message_dict: dict[str, Any] = {"role": role, "content": content}
                if "tool_calls" in msg:
                    message_dict["tool_calls"] = msg["tool_calls"]
                if "tool_call_id" in msg:
                    message_dict["tool_call_id"] = msg["tool_call_id"]
                messages.append(message_dict)

    return messages
