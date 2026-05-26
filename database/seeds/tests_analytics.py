"""Analytical seed — benchmark test history (Track B).

Inserts ~3 tests across the existing benchmarks so Eval-detail /
Test-list / Benchmark-dashboard pages have data on first load.

**Canonical-only**: uses ONLY the search/create black-boxes from
``app/tools/resources/<x>/search.py`` and
``app/tools/entries/<x>/create.py``. No inline SELECT or UPDATE.
Trade-off: every row stamps at ``now()`` because the canonical
creates don't accept ``created_at`` overrides; future enhancement
should add that param so this seed can spread the timeline.

Runner ordering: Phase 3 — runs after the eval module's benchmark
sync, so ``benchmark_entry`` + ``invocation_entry`` rows exist as
templates for the tests we materialize here.

Chain per test:
  session + activity/login metadata → group + group_name + parent run + parent call →
  test → benchmark_test → N × test_invocation (each with own run +
  call) → tokens + run_pricing → message + upload + text +
  text_completion + text_upload + message_upload (with real .txt
  files in UPLOAD_FOLDER so the transcript view renders) →
  trace + binding → (50%) completion + grade.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.benchmark.search import search_benchmarks
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.benchmark_test.refresh import refresh_benchmark_test
from app.tools.entries.calls.create import create_call
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation.search import search_invocations
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.messages.create import create_message
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.test.create import create_test
from app.tools.entries.test.refresh import refresh_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation_completion.create import (
    create_test_invocation_completion,
)
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.refresh import (
    refresh_test_invocation_runs,
)
from app.tools.entries.test_invocation_traces.create import (
    create_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.refresh import (
    refresh_test_invocation_traces,
)
from app.tools.entries.text_completion.create import create_text_completion
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text
from app.tools.entries.tokens.create import create_token
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.agents.search import search_agents
from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.rubrics.get import get_rubrics
from database.seeds.activity_sessions import ensure_activity_session
from database.seeds.ids import sid

TESTS_PER_RUN = 3
INVOCATIONS_PER_TEST = 4
COMPLETED_RATIO = 0.5


_USER_TURNS = [
    "Walk me through the rubric criterion you'd evaluate first.",
    "Now apply it to the candidate response.",
    "What's the score and the reasoning?",
]
_ASSISTANT_TURNS = [
    "I'll start with the criterion most likely to differentiate strong vs. weak responses.",
    "On this candidate response, the strongest evidence aligns with criterion two; criterion three is partially met.",
    "I'd score this 7/10. Strong on the analytical dimension, lighter on the application example.",
]
_SCORE_PCTS = [82, 71, 88, 64, 79, 93, 56, 75, 86, 90, 68, 84]
_TIME_TAKEN = [620, 940, 480, 1100, 760, 540, 1320, 850, 700, 580, 990, 720]
_TOKEN_ENVELOPES = [(1500, 850), (2200, 1100), (900, 520), (1800, 1300)]


def _score_from_percent(total_points: int | None, percent: int) -> int:
    """Convert demo percentages into raw rubric points."""
    if not total_points or total_points <= 0:
        return percent
    return max(0, min(total_points, round(total_points * percent / 100)))


def _resolve_template_agent_ids(
    template: object,
    *,
    agent_ids_by_model: dict[UUID, UUID],
    fallback_agent_ids: list[UUID],
    index: int,
) -> list[UUID]:
    """Mirror /test/invocation/create model_ids → agent_ids inheritance."""
    model_ids = list(getattr(template, "model_ids", None) or [])
    resolved = [
        agent_ids_by_model[model_id]
        for model_id in model_ids
        if model_id in agent_ids_by_model
    ]
    if resolved:
        return resolved
    return [fallback_agent_ids[index % len(fallback_agent_ids)]]


def _resolve_template_rubric_ids(
    template: object,
    *,
    rubric_ids_by_model_rubric: dict[UUID, UUID],
) -> list[UUID] | None:
    """Mirror /test/invocation/create model_rubric_ids → rubric_ids."""
    rubric_ids = [
        rubric_ids_by_model_rubric[model_rubric_id]
        for model_rubric_id in (getattr(template, "model_rubric_ids", None) or [])
        if model_rubric_id in rubric_ids_by_model_rubric
    ]
    return rubric_ids or None


def _write_transcript_file(upload_id: UUID, role: str, body: str) -> Path:
    """Write a tiny .txt to UPLOAD_FOLDER so the transcript view has
    real content. Filesystem write only — no SQL."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_FOLDER / f"{upload_id}.txt"
    path.write_text(f"[{role.upper()}] {body}\n", encoding="utf-8")
    return path


async def _seed_run_messages(
    conn: asyncpg.Connection,
    redis_client, *,
    run_id: UUID,
    session_id: UUID,
    slug: str,
) -> None:
    """Write the message → upload → text chain for the LLM transcript.
    Real .txt files written to UPLOAD_FOLDER (filesystem only)."""
    for turn_idx, (role, body) in enumerate(
        [
            ("user", _USER_TURNS[0]),
            ("assistant", _ASSISTANT_TURNS[0]),
            ("user", _USER_TURNS[1]),
            ("assistant", _ASSISTANT_TURNS[1]),
            ("user", _USER_TURNS[2]),
            ("assistant", _ASSISTANT_TURNS[2]),
        ]
    ):
        msg_id = sid(f"{slug}/msg/{turn_idx}")
        upload_id = sid(f"{slug}/upload/{turn_idx}")
        text_id = sid(f"{slug}/text/{turn_idx}")
        text_upload_id = sid(f"{slug}/text-upload/{turn_idx}")
        text_completion_id = sid(f"{slug}/text-completion/{turn_idx}")
        message_upload_id = sid(f"{slug}/msg-upload/{turn_idx}")

        file_path = _write_transcript_file(upload_id, role, body)
        size = file_path.stat().st_size

        await create_message(conn, redis_client, run_id=run_id, role=role, id=msg_id)
        await create_upload(
            conn,
            redis_client, session_id=session_id,
            file_path=str(file_path),
            mime_type="text/plain",
            size=size,
            id=upload_id,
        )
        await create_text(conn, redis_client, session_id=session_id, id=text_id)
        await create_text_upload(
            conn,
            redis_client, text_id=text_id,
            upload_id=upload_id,
            session_id=session_id,
            id=text_upload_id,
        )
        await create_text_completion(
            conn,
            redis_client, text_id=text_id,
            session_id=session_id,
            id=text_completion_id,
            stop=True,
            message=body,
        )
        await create_message_upload(
            conn,
            redis_client, message_id=msg_id,
            upload_id=upload_id,
            session_id=session_id,
            id=message_upload_id,
        )


async def _seed_one_test(
    conn: asyncpg.Connection,
    redis_client, *,
    test_idx: int,
    benchmarks: list,
    invocations_by_benchmark: dict[UUID, list],
    agent_ids: list[UUID],
    agent_ids_by_model: dict[UUID, UUID],
    rubric_ids_by_model_rubric: dict[UUID, UUID],
    rubric_map: dict[UUID, object],
    input_pricing_id: UUID | None,
    output_pricing_id: UUID | None,
    profile_id: UUID,
) -> bool:
    """Walk the canonical chain for one test."""
    if not benchmarks or not agent_ids:
        return False

    benchmark = benchmarks[test_idx % len(benchmarks)]
    benchmark_id = benchmark.benchmark_id
    template_invocations = invocations_by_benchmark.get(benchmark_id, [])[
        :INVOCATIONS_PER_TEST
    ]
    if not template_invocations:
        return False

    slug = f"tests-analytics/{test_idx}"
    test_id = sid(f"{slug}/test")
    test_call_id = sid(f"{slug}/test-call")
    test_run_id = sid(f"{slug}/test-run")
    group_id = sid(f"{slug}/group")
    group_name_id = sid(f"{slug}/group-name")
    seeded_session = await ensure_activity_session(
        conn,
        redis_client,
        slug=slug,
        profile_id=profile_id,
        label=f"Benchmark test seed #{test_idx + 1}",
        include_problem=test_idx == 1,
        include_grant=True,
        include_emulation=test_idx == 0,
    )
    session_id = seeded_session.session_id

    # Group + name + parent run/call (test_entry FKs to calls_entry).
    await create_group(
        conn, redis_client, session_id=session_id, artifact_type="test", id=group_id
    )
    await create_group_name(
        conn,
        redis_client, group_id=group_id,
        name=f"Benchmark test seed #{test_idx + 1}",
        session_id=session_id,
        id=group_name_id,
        generated=True,
    )
    await create_run(
        conn,
        redis_client, group_id=group_id,
        session_id=session_id,
        id=test_run_id,
        agent_ids=[agent_ids[0]],
    )
    await create_call(
        conn, redis_client, run_id=test_run_id, session_id=session_id, id=test_call_id
    )
    await create_test(
        conn,
        redis_client, id=test_id,
        call_id=test_call_id,
        profiles_id=profile_id,
        name=f"Seed benchmark test #{test_idx + 1}",
        description="Seeded test for analytics dashboards",
        num_invocations=len(template_invocations),
        is_dynamic=True,
    )
    await create_benchmark_test(
        conn, redis_client, benchmark_id=benchmark_id, test_id=test_id, session_id=session_id
    )

    for inv_idx, template_invocation in enumerate(template_invocations):
        completed = inv_idx < int(INVOCATIONS_PER_TEST * COMPLETED_RATIO)
        agent_ids_for_invocation = _resolve_template_agent_ids(
            template_invocation,
            agent_ids_by_model=agent_ids_by_model,
            fallback_agent_ids=agent_ids,
            index=inv_idx,
        )
        rubric_ids_for_invocation = _resolve_template_rubric_ids(
            template_invocation,
            rubric_ids_by_model_rubric=rubric_ids_by_model_rubric,
        )
        rubric_id = (rubric_ids_for_invocation or [None])[0]
        rubric = rubric_map.get(rubric_id) if rubric_id else None

        inv_slug = f"{slug}/inv/{inv_idx}"
        ti_id = sid(f"{inv_slug}/test-invocation")
        ti_call_id = sid(f"{inv_slug}/ti-call")
        ti_run_id = sid(f"{inv_slug}/ti-run")
        trace_id = sid(f"{inv_slug}/trace")
        binding_id = sid(f"{inv_slug}/binding")
        completion_id = sid(f"{inv_slug}/completion")
        completion_call_id = sid(f"{inv_slug}/completion-call")
        grade_id = sid(f"{inv_slug}/grade")
        grade_call_id = sid(f"{inv_slug}/grade-call")

        await create_run(
            conn,
            redis_client, group_id=group_id,
            session_id=session_id,
            id=ti_run_id,
            agent_ids=agent_ids_for_invocation,
        )
        await create_call(
            conn, redis_client, run_id=ti_run_id, session_id=session_id, id=ti_call_id
        )
        await create_test_invocation(
            conn,
            redis_client, id=ti_id,
            test_id=test_id,
            call_id=ti_call_id,
            title=f"Invocation {(template_invocation.position or inv_idx) + 1}",
            use_custom=bool(template_invocation.use_custom),
            position=template_invocation.position or inv_idx,
            agent_ids=agent_ids_for_invocation,
            rubric_ids=rubric_ids_for_invocation,
            quality_ids=template_invocation.quality_ids or None,
            department_ids=template_invocation.department_ids or None,
            voice_ids=template_invocation.voice_ids or None,
            reasoning_level_ids=template_invocation.reasoning_level_ids or None,
            temperature_level_ids=(
                template_invocation.temperature_level_ids or None
            ),
            modality_ids=template_invocation.modality_ids or None,
        )

        inp, out = _TOKEN_ENVELOPES[inv_idx % len(_TOKEN_ENVELOPES)]
        await create_token(
            conn,
            redis_client, run_id=ti_run_id,
            session_id=session_id,
            id=sid(f"{inv_slug}/token"),
            input_tokens=inp,
            output_tokens=out,
        )
        if input_pricing_id is not None:
            await create_run_pricing_entry_internal(
                conn,
                redis_client, session_id=session_id,
                pricing_type="input",
                run_id=ti_run_id,
                pricing_id=input_pricing_id,
                count=inp,
            )
        if output_pricing_id is not None:
            await create_run_pricing_entry_internal(
                conn,
                redis_client, session_id=session_id,
                pricing_type="output",
                run_id=ti_run_id,
                pricing_id=output_pricing_id,
                count=out,
            )

        await _seed_run_messages(
            conn, redis_client, run_id=ti_run_id, session_id=session_id, slug=inv_slug
        )

        await create_test_invocation_traces(
            conn,
            redis_client, test_invocation_id=ti_id,
            id=trace_id,
            run_id=ti_run_id,
            reasoning_level_ids=template_invocation.reasoning_level_ids or None,
            temperature_level_ids=(
                template_invocation.temperature_level_ids or None
            ),
            voice_ids=template_invocation.voice_ids or None,
            quality_ids=template_invocation.quality_ids or None,
            modality_ids=template_invocation.modality_ids or None,
        )
        await create_test_invocation_runs(
            conn,
            redis_client, test_invocation_id=ti_id,
            id=binding_id,
            run_id=ti_run_id,
            test_invocation_traces_id=trace_id,
        )

        if completed:
            for cid in (completion_call_id, grade_call_id):
                await create_call(
                    conn, redis_client, run_id=ti_run_id, session_id=session_id, id=cid
                )
            await create_test_invocation_completion(
                conn,
                redis_client, invocation_id=ti_id,
                call_id=completion_call_id,
                id=completion_id,
                stop=True,
            )
            score_pct = _SCORE_PCTS[
                (test_idx * INVOCATIONS_PER_TEST + inv_idx) % len(_SCORE_PCTS)
            ]
            score = _score_from_percent(
                getattr(rubric, "total_points", None),
                score_pct,
            )
            time_taken = _TIME_TAKEN[
                (test_idx * INVOCATIONS_PER_TEST + inv_idx) % len(_TIME_TAKEN)
            ]
            await create_test_grade(
                conn,
                redis_client, invocation_id=ti_id,
                call_id=grade_call_id,
                time_taken=time_taken,
                passed=score >= (getattr(rubric, "pass_points", None) or 0),
                score=score,
                id=grade_id,
            )

    return True


async def seed(pool: asyncpg.Pool, redis: Redis) -> None:
    """Entry point — discover via canonical search, fan out N tests."""
    inserted = 0
    async with pool.acquire() as conn:
        # ── Discovery via canonical search black-boxes ─────────────
        # MVs are refreshed by the runner before this seed runs (see
        # runner.py "Phase 3 — Analytical seeds" block).
        benchmarks = await search_benchmarks(conn, redis, limit=12)
        agents = await search_agents(conn, redis, limit_count=4, bypass_cache=True)
        profiles = await search_profiles(conn, redis, limit_count=1, bypass_cache=True)
        input_pricings = await search_pricing(
            conn, redis, pricing_type="input", limit_count=4, bypass_cache=True
        )
        output_pricings = await search_pricing(
            conn, redis, pricing_type="output", limit_count=4, bypass_cache=True
        )
        print(
            f"  (discovery: benchmarks={len(benchmarks)}, "
            f"agents={len(agents)}, profiles={len(profiles)}, "
            f"input_pricings={len(input_pricings)}, "
            f"output_pricings={len(output_pricings)})"
        )

        if not benchmarks or not agents or not profiles:
            print(
                "  (skipped: need at least one benchmark, agent, and "
                "profile to seed tests)"
            )
            return

        # Per-benchmark invocation lookup — search_invocations supports
        # benchmark_ids filter so we get exactly what each test needs.
        invocations_by_benchmark: dict[UUID, list] = {}
        for b in benchmarks[:TESTS_PER_RUN]:
            inv_rows = await search_invocations(
                conn, redis, benchmark_ids=[b.benchmark_id], limit=INVOCATIONS_PER_TEST
            )
            invocations_by_benchmark[b.benchmark_id] = inv_rows

        model_rubric_ids = list(
            {
                model_rubric_id
                for inv_rows in invocations_by_benchmark.values()
                for invocation in inv_rows
                for model_rubric_id in (invocation.model_rubric_ids or [])
            }
        )
        model_rubrics = await get_model_rubrics(
            conn, model_rubric_ids, redis, bypass_cache=True
        )
        rubric_ids_by_model_rubric = {
            model_rubric.id: model_rubric.rubric_id
            for model_rubric in model_rubrics
            if model_rubric.id and model_rubric.rubric_id
        }
        rubric_ids = list(set(rubric_ids_by_model_rubric.values()))
        rubric_map = {
            rubric.id: rubric
            for rubric in await get_rubrics(conn, rubric_ids, redis, bypass_cache=True)
            if rubric.id
        }

        agent_ids = [a.id for a in agents]
        agent_ids_by_model = {
            agent.model_id: agent.id
            for agent in agents
            if agent.model_id and agent.id
        }
        input_pricing_id = input_pricings[0].id if input_pricings else None
        output_pricing_id = output_pricings[0].id if output_pricings else None
        profile_id = profiles[0].id

        for test_idx in range(TESTS_PER_RUN):
            try:
                async with conn.transaction():
                    seeded = await _seed_one_test(
                        conn,
                        redis, test_idx=test_idx,
                        benchmarks=benchmarks,
                        invocations_by_benchmark=invocations_by_benchmark,
                        agent_ids=agent_ids,
                        agent_ids_by_model=agent_ids_by_model,
                        rubric_ids_by_model_rubric=rubric_ids_by_model_rubric,
                        rubric_map=rubric_map,
                        input_pricing_id=input_pricing_id,
                        output_pricing_id=output_pricing_id,
                        profile_id=profile_id,
                    )
                if seeded:
                    inserted += 1
                else:
                    print(f"  (test #{test_idx} skipped: no template invocations)")
            except Exception as e:
                print(f"  (test #{test_idx} skipped: {e})")
                continue

        if inserted:
            for refresh in (
                refresh_benchmark_test,
                refresh_test,
                refresh_test_invocation_traces,
                refresh_test_invocation_runs,
                refresh_test_invocation,
            ):
                try:
                    await refresh(conn)
                except Exception as e:
                    print(f"  ({refresh.__name__} skipped: {e})")

    print(f"  OK: {inserted}/{TESTS_PER_RUN} tests seeded")
