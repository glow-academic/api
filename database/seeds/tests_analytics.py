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
  group + group_name + parent run + parent call →
  test → benchmark_test → N × test_invocation (each with own run +
  call) → tokens + run_pricing → message + upload + text +
  text_completion + text_upload + message_upload (with real .txt
  files in UPLOAD_FOLDER so the transcript view renders) →
  trace + binding → (50%) completion + grade.
"""

from __future__ import annotations

import asyncpg
from pathlib import Path
from redis.asyncio import Redis
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.benchmark.search import search_benchmarks
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.calls.create import create_call
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation.search import search_invocations
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.messages.create import create_message
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.test.create import create_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_completion.create import (
    create_test_invocation_completion,
)
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)
from app.tools.entries.test_invocation_traces.create import (
    create_test_invocation_traces,
)
from app.tools.entries.text_completion.create import create_text_completion
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text
from app.tools.entries.tokens.create import create_token
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.agents.search import search_agents
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.profiles.search import search_profiles

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
_SCORES = [82, 71, 88, 64, 79, 93, 56, 75, 86, 90, 68, 84]
_TIME_TAKEN = [620, 940, 480, 1100, 760, 540, 1320, 850, 700, 580, 990, 720]
_TOKEN_ENVELOPES = [(1500, 850), (2200, 1100), (900, 520), (1800, 1300)]


def _write_transcript_file(upload_id: UUID, role: str, body: str) -> Path:
    """Write a tiny .txt to UPLOAD_FOLDER so the transcript view has
    real content. Filesystem write only — no SQL."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_FOLDER / f"{upload_id}.txt"
    path.write_text(f"[{role.upper()}] {body}\n", encoding="utf-8")
    return path


async def _seed_run_messages(
    conn: asyncpg.Connection,
    *,
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

        await create_message(conn, run_id=run_id, role=role, id=msg_id)
        await create_upload(
            conn,
            session_id=session_id,
            file_path=str(file_path),
            mime_type="text/plain",
            size=size,
            id=upload_id,
        )
        await create_text(conn, session_id=session_id, id=text_id)
        await create_text_upload(
            conn,
            text_id=text_id,
            upload_id=upload_id,
            session_id=session_id,
            id=text_upload_id,
        )
        await create_text_completion(
            conn,
            text_id=text_id,
            session_id=session_id,
            id=text_completion_id,
            stop=True,
            message=body,
        )
        await create_message_upload(
            conn,
            message_id=msg_id,
            upload_id=upload_id,
            session_id=session_id,
            id=message_upload_id,
        )


async def _seed_one_test(
    conn: asyncpg.Connection,
    *,
    test_idx: int,
    benchmarks: list,
    invocations_by_benchmark: dict[UUID, list[UUID]],
    agent_ids: list[UUID],
    input_pricing_id: UUID | None,
    output_pricing_id: UUID | None,
    profile_id: UUID,
) -> None:
    """Walk the canonical chain for one test."""
    if not benchmarks or not agent_ids:
        return

    benchmark = benchmarks[test_idx % len(benchmarks)]
    benchmark_id = benchmark.benchmark_id
    template_invocations = invocations_by_benchmark.get(benchmark_id, [])[
        :INVOCATIONS_PER_TEST
    ]

    slug = f"tests-analytics/{test_idx}"
    test_id = sid(f"{slug}/test")
    test_call_id = sid(f"{slug}/test-call")
    test_run_id = sid(f"{slug}/test-run")
    group_id = sid(f"{slug}/group")
    group_name_id = sid(f"{slug}/group-name")
    session_id = profile_id

    # Group + name + parent run/call (test_entry FKs to calls_entry).
    await create_group(
        conn, session_id=session_id, artifact_type="test", id=group_id
    )
    await create_group_name(
        conn,
        group_id=group_id,
        name=f"Benchmark test seed #{test_idx + 1}",
        session_id=session_id,
        id=group_name_id,
        generated=True,
    )
    await create_run(
        conn,
        group_id=group_id,
        session_id=session_id,
        id=test_run_id,
        agent_ids=[agent_ids[0]],
    )
    await create_call(
        conn, run_id=test_run_id, session_id=session_id, id=test_call_id
    )
    await create_test(
        conn,
        id=test_id,
        call_id=test_call_id,
        profiles_id=profile_id,
        name=f"Seed benchmark test #{test_idx + 1}",
        description="Seeded test for analytics dashboards",
        num_invocations=len(template_invocations),
        is_dynamic=True,
    )
    await create_benchmark_test(
        conn, benchmark_id=benchmark_id, test_id=test_id, session_id=session_id
    )

    for inv_idx, _template_inv_id in enumerate(template_invocations):
        completed = inv_idx < int(INVOCATIONS_PER_TEST * COMPLETED_RATIO)
        agent_for_inv = agent_ids[inv_idx % len(agent_ids)]

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
            group_id=group_id,
            session_id=session_id,
            id=ti_run_id,
            agent_ids=[agent_for_inv],
        )
        await create_call(
            conn, run_id=ti_run_id, session_id=session_id, id=ti_call_id
        )
        await create_test_invocation(
            conn,
            id=ti_id,
            test_id=test_id,
            call_id=ti_call_id,
            title=f"Invocation {inv_idx + 1}",
            position=inv_idx,
            agent_ids=[agent_for_inv],
        )

        inp, out = _TOKEN_ENVELOPES[inv_idx % len(_TOKEN_ENVELOPES)]
        await create_token(
            conn,
            run_id=ti_run_id,
            session_id=session_id,
            id=sid(f"{inv_slug}/token"),
            input_tokens=inp,
            output_tokens=out,
        )
        if input_pricing_id is not None:
            await create_run_pricing_entry_internal(
                conn,
                session_id=session_id,
                pricing_type="input",
                run_id=ti_run_id,
                pricing_id=input_pricing_id,
                count=inp,
            )
        if output_pricing_id is not None:
            await create_run_pricing_entry_internal(
                conn,
                session_id=session_id,
                pricing_type="output",
                run_id=ti_run_id,
                pricing_id=output_pricing_id,
                count=out,
            )

        await _seed_run_messages(
            conn, run_id=ti_run_id, session_id=session_id, slug=inv_slug
        )

        await create_test_invocation_traces(
            conn, test_invocation_id=ti_id, id=trace_id, run_id=ti_run_id
        )
        await create_test_invocation_runs(
            conn,
            test_invocation_id=ti_id,
            id=binding_id,
            run_id=ti_run_id,
            test_invocation_traces_id=trace_id,
        )

        if completed:
            for cid in (completion_call_id, grade_call_id):
                await create_call(
                    conn, run_id=ti_run_id, session_id=session_id, id=cid
                )
            await create_test_invocation_completion(
                conn,
                invocation_id=ti_id,
                call_id=completion_call_id,
                id=completion_id,
                stop=True,
            )
            score = _SCORES[(test_idx * INVOCATIONS_PER_TEST + inv_idx) % len(_SCORES)]
            time_taken = _TIME_TAKEN[
                (test_idx * INVOCATIONS_PER_TEST + inv_idx) % len(_TIME_TAKEN)
            ]
            await create_test_grade(
                conn,
                invocation_id=ti_id,
                call_id=grade_call_id,
                time_taken=time_taken,
                passed=score >= 60,
                score=score,
                id=grade_id,
            )


async def seed(pool: asyncpg.Pool, redis: Redis) -> None:
    """Entry point — discover via canonical search, fan out N tests."""
    inserted = 0
    async with pool.acquire() as conn:
        # ── Discovery via canonical search black-boxes ─────────────
        # MVs are refreshed by the runner before this seed runs (see
        # runner.py "Phase 3 — Analytical seeds" block).
        benchmarks = await search_benchmarks(conn, limit=12)
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
        invocations_by_benchmark: dict[UUID, list[UUID]] = {}
        for b in benchmarks[:TESTS_PER_RUN]:
            inv_rows = await search_invocations(
                conn, benchmark_ids=[b.benchmark_id], limit=INVOCATIONS_PER_TEST
            )
            invocations_by_benchmark[b.benchmark_id] = [r.id for r in inv_rows]

        agent_ids = [a.id for a in agents]
        input_pricing_id = input_pricings[0].id if input_pricings else None
        output_pricing_id = output_pricings[0].id if output_pricings else None
        profile_id = profiles[0].id

        async with conn.transaction():
            for test_idx in range(TESTS_PER_RUN):
                try:
                    await _seed_one_test(
                        conn,
                        test_idx=test_idx,
                        benchmarks=benchmarks,
                        invocations_by_benchmark=invocations_by_benchmark,
                        agent_ids=agent_ids,
                        input_pricing_id=input_pricing_id,
                        output_pricing_id=output_pricing_id,
                        profile_id=profile_id,
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  (test #{test_idx} skipped: {e})")
                    continue

    print(f"  OK: {inserted}/{TESTS_PER_RUN} tests seeded")
