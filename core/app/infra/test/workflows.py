"""Shared test workflow logic, transport-agnostic apart from emitted payload shape."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
from redis.asyncio import Redis

from app.infra.websocket.socket_event import EmitFn, client_event, internal_event


async def test_progress_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
) -> None:
    """Translate test_progress_update to test_grade_start."""
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
                "test_grade_start",
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
                "test_run_complete",
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
                "test_error",
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
                    conn,
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
                    "test_grade_progress",
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


def _find_next_run_id(runs: list[Any], prev_run_id: Any) -> Any:
    """Find the next run after prev_run_id in a sorted list of runs."""
    if not runs:
        return None
    if prev_run_id is None:
        return runs[0].run_id
    found = False
    for run in runs:
        if found:
            return run.run_id
        if run.run_id == prev_run_id:
            found = True
    return None


async def test_group_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Orchestrate sequential runs within a group."""
    from app.infra.websocket.test_types import TestErrorData
    from app.infra.test.client_types import TestGroupPayload
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

        async with pool.acquire() as conn:
            runs, _ = await search_runs(
                conn,
                group_ids=[group_id],
                sort_order="asc",
                bypass_mv=True,
                limit=1000,
            )

        next_run_id = _find_next_run_id(runs, prev_run_id)
        if not next_run_id:
            await emit(
                [
                    internal_event(
                        "test_group_complete",
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
                    "test_run",
                    {
                        "sid": sid,
                        "profile_id": profile_id_str,
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
                    "test_error",
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
                    "test_error",
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
        async with pool.acquire() as conn:
            invocations, _total_count = await search_test_invocation_entries_internal(
                conn,
                test_ids=[test_id],
                limit=1000,
                bypass_mv=True,
            )
    except Exception as e:
        logger.exception(f"Error in test_next: {e}")
        await emit(
            [
                client_event(
                    "test_error",
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
                            "test_error",
                            {
                                "message": "Failed to find group for next test invocation",
                                "error_type": "internal",
                            },
                            room=sid,
                        )
                    ]
                )
                return
            await emit(
                [
                    internal_event(
                        "test_group",
                        {
                            "sid": sid,
                            "profile_id": data.get("profile_id"),
                            "test_invocation_id": str(invocation.invocation_id),
                            "test_id": str(test_id),
                            "group_id": str(invocation.group_id),
                        },
                    )
                ]
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
    from app.infra.websocket.test_types import TestErrorData, TestProceedData
    from app.tools.entries.benchmark_test.create import create_benchmark_test
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.sessions.create import create_session
    from app.tools.entries.test.create import create_test
    from app.tools.entries.test_invocation.refresh import (
        refresh_test_invocation,
    )
    from app.utils.cache.invalidate_tags import invalidate_tags
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)
    sid = data.get("sid", "")

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        return

    try:
        uuid.UUID(profile_id_str)
    except Exception as e:
        logger.exception(f"Invalid profile_id in test_start: {e}")
        return

    benchmark_id_raw = data.get("benchmark_id")
    benchmark_id = uuid.UUID(str(benchmark_id_raw)) if benchmark_id_raw else None
    infinite_mode = data.get("infinite_mode", False)
    profiles_id_str = data.get("profiles_id")
    if not profiles_id_str:
        logger.error("profiles_id missing from test_start payload")
        return

    session_id_str = data.get("session_id")

    try:
        profiles_id = uuid.UUID(profiles_id_str)

        async with pool.acquire() as conn:
            session_id = (
                uuid.UUID(session_id_str)
                if session_id_str
                else (await create_session(conn, profile_id=profiles_id)).id
            )
            group_id = (await create_group(conn, session_id=session_id)).id
            run_id = (
                await create_run(
                    conn,
                    group_id=group_id,
                    session_id=session_id,
                    profiles_id=profiles_id,
                )
            ).id
            call_id = (await create_call(conn, run_id=run_id, session_id=session_id)).id
            result = await create_test(
                conn,
                call_id=call_id,
                profiles_id=profiles_id,
                infinite_mode=infinite_mode,
            )
            test_id = result.id

            if benchmark_id:
                await create_benchmark_test(
                    conn,
                    benchmark_id=benchmark_id,
                    test_id=test_id,
                    session_id=session_id,
                )

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

            await refresh_test_invocation(conn)
            if redis:
                await invalidate_tags(["test", "tests", "benchmark"], redis=redis)

        await emit(
            [
                internal_event(
                    "test_proceed",
                    TestProceedData(sid=sid, test_id=str(test_id)).model_dump(
                        mode="json"
                    ),
                )
            ]
        )

    except Exception as e:
        logger.exception(f"Error in test_start: {e}")
        await emit(
            [
                internal_event(
                    "test_error",
                    TestErrorData(
                        sid=sid,
                        message=f"Failed to start test: {e}",
                        error_type="start",
                    ).model_dump(mode="json"),
                )
            ]
        )


async def test_proceed_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis | None = None,
) -> None:
    """Shared core: resolve context, check done, resolve invocation, emit."""
    from app.infra.websocket.test_types import TestErrorData, TestProceedData
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.sessions.create import create_session
    from app.tools.entries.test.get import get_tests
    from app.tools.entries.test_invocation.create import (
        create_test_invocation,
    )
    from app.tools.entries.test_invocation.refresh import (
        refresh_test_invocation,
    )
    from app.tools.entries.test_invocation.search import (
        search_test_invocation_entries_internal,
    )
    from app.tools.entries.test_invocation_completion.create import (
        create_test_invocation_completion,
    )
    from app.utils.cache.invalidate_tags import invalidate_tags
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)

    async def _create_run_call(
        conn: asyncpg.Connection,
        *,
        invocation_id: uuid.UUID | None = None,
        group_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        if invocation_id is not None:
            invocation_call_id = await conn.fetchval(
                "SELECT call_id FROM test_invocation_entry WHERE id = $1",
                invocation_id,
            )
            if invocation_call_id is not None:
                return invocation_call_id

        session_id = None
        if group_id is not None:
            session_id = await conn.fetchval(
                "SELECT session_id FROM groups_entry WHERE id = $1",
                group_id,
            )

        if session_id is None:
            session = await create_session(conn)
            group = await create_group(conn, session_id=session.id)
            run = await create_run(conn, group_id=group.id, session_id=session.id)
            call = await create_call(conn, run_id=run.id, session_id=session.id)
            return call.id

        run = await create_run(conn, group_id=group_id, session_id=session_id)
        call = await create_call(conn, run_id=run.id, session_id=session_id)
        return call.id

    sid = data.get("sid", "")

    try:
        payload = TestProceedData(**data)
    except Exception as e:
        logger.exception(f"Invalid test_proceed payload: {e}")
        return

    try:
        test_id = uuid.UUID(payload.test_id)
        force_proceed = payload.force_proceed
        completed_invocation_id = (
            uuid.UUID(payload.completed_invocation_id)
            if payload.completed_invocation_id
            else None
        )
        complete_all = payload.complete_all

        async with pool.acquire() as conn:
            if completed_invocation_id:
                try:
                    completion_call_id = await _create_run_call(
                        conn,
                        invocation_id=completed_invocation_id,
                    )
                    await create_test_invocation_completion(
                        conn,
                        invocation_id=completed_invocation_id,
                        call_id=completion_call_id,
                    )
                except Exception:
                    logger.warning(
                        f"Failed to create test_completion for {completed_invocation_id} "
                        f"(may already exist)"
                    )

            if complete_all:
                (
                    all_invocations,
                    _total_count,
                ) = await search_test_invocation_entries_internal(
                    conn,
                    test_ids=[test_id],
                    limit=1000,
                    bypass_mv=True,
                )
                for inv in all_invocations:
                    if not inv.invocation_completed:
                        try:
                            completion_call_id = await _create_run_call(
                                conn,
                                invocation_id=inv.invocation_id,
                            )
                            await create_test_invocation_completion(
                                conn,
                                invocation_id=inv.invocation_id,
                                call_id=completion_call_id,
                            )
                        except Exception:
                            pass
                await refresh_test_invocation(conn)
                if redis:
                    await invalidate_tags(["test", "tests", "benchmark"], redis=redis)

                await emit(
                    [
                        internal_event(
                            "test_ended",
                            {
                                "sid": sid,
                                "test_id": str(test_id),
                                "success": True,
                                "message": "All invocations completed",
                            },
                        )
                    ]
                )
                return

            (
                all_invocations,
                _total_count,
            ) = await search_test_invocation_entries_internal(
                conn,
                test_ids=[test_id],
                limit=1000,
                bypass_mv=True,
            )
            tests = await get_tests(conn, ids=[test_id])

        is_dynamic = tests[0].is_dynamic if tests else True
        total_invocations = len(all_invocations)
        completed = [inv for inv in all_invocations if inv.invocation_completed]
        uncompleted = [inv for inv in all_invocations if not inv.invocation_completed]
        completed_count = len(completed)

        if not all_invocations:
            await emit(
                [
                    internal_event(
                        "test_error",
                        TestErrorData(
                            sid=sid,
                            message="Failed to resolve test context",
                            error_type="proceed",
                        ).model_dump(mode="json"),
                    )
                ]
            )
            return

        if not uncompleted or completed_count >= total_invocations:
            await emit(
                [
                    internal_event(
                        "test_ended",
                        {
                            "sid": sid,
                            "test_id": str(test_id),
                            "success": True,
                            "message": "All invocations completed",
                        },
                    )
                ]
            )
            return

        next_invocation = uncompleted[0]

        if next_invocation.use_custom and not force_proceed:
            await emit(
                [
                    internal_event(
                        "test_started",
                        {
                            "sid": sid,
                            "test_id": str(test_id),
                            "invocation_entry_id": str(next_invocation.invocation_id),
                        },
                    )
                ]
            )
            return

        async with pool.acquire() as conn:
            invocation_call_id = await _create_run_call(
                conn,
                group_id=next_invocation.group_id,
            )
            inv_result = await create_test_invocation(
                conn,
                test_id=test_id,
                call_id=invocation_call_id,
                group_id=next_invocation.group_id,
            )
            test_invocation_id = inv_result.id
            await refresh_test_invocation(conn)
            if redis:
                await invalidate_tags(["test", "tests", "benchmark"], redis=redis)

        await emit(
            [
                internal_event(
                    "test_invocation_started",
                    {
                        "sid": sid,
                        "test_id": str(test_id),
                        "test_invocation_id": str(test_invocation_id),
                        "is_dynamic": is_dynamic,
                    },
                )
            ]
        )

    except Exception as e:
        logger.exception(f"Error in test_proceed: {e}")
        await emit(
            [
                internal_event(
                    "test_error",
                    TestErrorData(
                        sid=sid,
                        message=f"Failed to proceed: {e}",
                        error_type="proceed",
                    ).model_dump(mode="json"),
                )
            ]
        )


async def test_run_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
) -> None:
    """Copy conversation from original run, create new run, emit generate_artifact."""
    from app.infra.websocket.test_types import TestErrorData
    from app.infra.test.client_types import TestRunPayload
    from app.tools.entries.messages.create import create_message
    from app.tools.entries.messages.search import search_messages
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.test_invocation.get import get_test_invocations
    from app.utils.logging.db_logger import get_logger

    logger = get_logger(__name__)
    sid = data.get("sid", "")

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        return

    try:
        payload = TestRunPayload(**data)
    except Exception as e:
        logger.exception(f"Invalid test_run payload: {e}")
        return

    try:
        test_id = payload.test_id
        test_invocation_id = payload.test_invocation_id
        original_run_id = payload.run_id

        async with pool.acquire() as conn:
            invocations = await get_test_invocations(
                conn, ids=[test_invocation_id], bypass_mv=True
            )
            if not invocations:
                await emit(
                    [
                        internal_event(
                            "test_error",
                            TestErrorData(
                                sid=sid,
                                invocation_id=str(test_invocation_id),
                                message="No group found for test invocation",
                                error_type="run",
                            ).model_dump(mode="json"),
                        )
                    ]
                )
                return

            group_id = invocations[0].group_id
            session_id_str = data.get("session_id")
            session_id = (
                uuid.UUID(session_id_str) if session_id_str else uuid.UUID(int=0)
            )
            profiles_id_str = data.get("profiles_id")
            profiles_id = uuid.UUID(profiles_id_str) if profiles_id_str else None

            run_result = await create_run(
                conn,
                group_id=group_id,
                session_id=session_id,
                profiles_id=profiles_id,
            )
            new_run_id = run_result.id

            original_messages, _ = await search_messages(
                conn,
                run_ids=[original_run_id],
                sort_order="asc",
                bypass_mv=True,
                limit=1000,
            )
            if not original_messages:
                await emit(
                    [
                        internal_event(
                            "test_error",
                            TestErrorData(
                                sid=sid,
                                invocation_id=str(test_invocation_id),
                                message="No messages found in original run",
                                error_type="run",
                            ).model_dump(mode="json"),
                        )
                    ]
                )
                return

            messages_to_copy = list(original_messages)
            for i in range(len(messages_to_copy) - 1, -1, -1):
                if messages_to_copy[i].role == "assistant":
                    messages_to_copy.pop(i)
                    break

            for msg in messages_to_copy:
                await create_message(conn, run_id=new_run_id, role=msg.role)

            assistant_msg = await create_message(
                conn,
                run_id=new_run_id,
                role="assistant",
            )

        await emit(
            [
                internal_event(
                    "test_run_started",
                    {
                        "sid": sid,
                        "test_id": str(test_id),
                        "test_invocation_id": str(test_invocation_id),
                        "run_id": str(new_run_id),
                        "original_run_id": str(original_run_id),
                        "message_id": str(assistant_msg.id),
                    },
                )
            ]
        )

        await emit(
            [
                internal_event(
                    "generate_artifact",
                    {
                        "sid": sid,
                        "artifact_type": "test",
                        "resource_type": "test",
                        "modality": "text",
                        "run_id": str(new_run_id),
                        "group_id": str(group_id),
                        "chat_id": str(test_invocation_id),
                        "messages": [],
                        "llm_config": {},
                        "tools": [],
                        "metadata": {
                            "test_id": str(test_id),
                            "test_invocation_id": str(test_invocation_id),
                            "original_run_id": str(original_run_id),
                        },
                    },
                )
            ]
        )

        logger.info(
            f"Test run started - test_id={test_id}, "
            f"invocation_id={test_invocation_id}, "
            f"new_run_id={new_run_id}, original_run_id={original_run_id}"
        )

    except Exception as e:
        logger.exception(f"Error in test_run: {e}")
        await emit(
            [
                internal_event(
                    "test_error",
                    TestErrorData(
                        sid=sid,
                        invocation_id=str(payload.test_invocation_id),
                        message=f"Failed to run test: {e}",
                        error_type="run",
                    ).model_dump(mode="json"),
                )
            ]
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test domain utilities (moved from app.socket.v5.types)
# ═══════════════════════════════════════════════════════════════════════════


def determine_next_run(
    invocation_run_ids: list[uuid.UUID],
    run_ids: list[uuid.UUID],
) -> tuple[uuid.UUID | None, int, int]:
    """Determine the next pending template run to replay.

    Compares configured template runs (run_ids) against completed runs
    (invocation_run_ids) to find the next unexecuted template.

    Returns:
        (next_run_resource_id, current_run_number, total_runs)
    """
    total_runs = len(run_ids)
    completed_runs = len(invocation_run_ids)

    if completed_runs >= total_runs:
        return None, total_runs, total_runs

    next_run_resource_id = (
        run_ids[completed_runs] if completed_runs < total_runs else None
    )
    current_run = completed_runs + 1

    return next_run_resource_id, current_run, total_runs


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
