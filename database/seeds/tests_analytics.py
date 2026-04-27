"""Analytical seed — benchmark test history (Track B).

Inserts ~3 tests across the existing evals so Eval-detail / Test-list /
Benchmark-dashboard pages have data on first load. Each test fans out
across the existing benchmark template invocations (model_ids → agents)
and produces a mix of completed (with grades) and pending invocations.

Uses canonical entry create black-boxes only — no inline SQL. Discovers
benchmarks/agents/models/pricings at runtime so the seed adapts to
whatever resource set the host setup happens to have.

Chain per test:
  test → benchmark_test → groups + group_names → invocation_entry
  (template, already exists from sync_benchmark_entries) →
  test_invocation_entry × N →
    runs_entry + tokens_entry + run_pricing_entry (drives Pricing)
    + messages_entry + uploads + texts + text_completion +
    text_uploads + message_uploads (drives transcript view)
    + test_invocation_traces_entry + test_invocation_runs_entry
    + test_invocation_completion_entry + test_grade_entry (when
    completed — 50% of invocations)

LLM-transcript .txt files are written into UPLOAD_FOLDER so the
transcript view actually renders content. Files are tiny (~3 lines
each) and deterministic — re-seeding overwrites them in place.
"""

from __future__ import annotations

import asyncpg
from datetime import datetime, timedelta, timezone
from pathlib import Path
from redis.asyncio import Redis
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.benchmark_test.create import create_benchmark_test
from app.tools.entries.calls.create import create_call
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
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

from database.seeds.ids import sid


TESTS_PER_RUN = 3
INVOCATIONS_PER_TEST = 4
COMPLETED_RATIO = 0.5  # 50% of invocations are graded


# Per-(test_idx, invocation_idx) deterministic transcript content.
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


_TOKEN_ENVELOPES = [
    (1500, 850),
    (2200, 1100),
    (900, 520),
    (1800, 1300),
]


async def _fetch_seed_inputs(
    pool: asyncpg.Pool,
) -> tuple[
    list[tuple[UUID, UUID]],  # (benchmark_id, invocation_template_id) pairs
    list[UUID],               # agent_ids (for runs)
    list[UUID],               # pricing_ids
    UUID | None,              # primary profile id (for test creation)
]:
    async with pool.acquire() as conn:
        # Benchmark templates: every active benchmark with at least
        # one active invocation_entry. Pull invocation pairs (one per
        # benchmark, multiple if the benchmark has multiple invocations).
        rows = await conn.fetch(
            """
            SELECT b.id AS benchmark_id, i.id AS invocation_id
            FROM benchmark_entry b
            JOIN invocation_entry i ON i.benchmark_id = b.id AND i.active = true
            WHERE b.active = true
            ORDER BY b.created_at, i.created_at
            LIMIT 12
            """
        )
        benchmark_invocations = [(r["benchmark_id"], r["invocation_id"]) for r in rows]

        agent_rows = await conn.fetch(
            "SELECT id FROM agents_resource WHERE active=true ORDER BY created_at LIMIT 4"
        )
        agent_ids = [r["id"] for r in agent_rows]

        pricing_rows = await conn.fetch(
            "SELECT id FROM pricing_resource WHERE active=true "
            "AND pricing_type IN ('input', 'output') "
            "ORDER BY pricing_type, created_at LIMIT 6"
        )
        pricing_ids = [r["id"] for r in pricing_rows]

        profile_row = await conn.fetchrow(
            "SELECT id FROM profiles_resource WHERE active=true ORDER BY created_at LIMIT 1"
        )
        profile_id = profile_row["id"] if profile_row else None

    return benchmark_invocations, agent_ids, pricing_ids, profile_id


def _write_transcript_file(upload_id: UUID, role: str, body: str) -> Path:
    """Write a tiny .txt to UPLOAD_FOLDER so the transcript view has
    real content. Path returned matches what create_upload stores."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_FOLDER / f"{upload_id}.txt"
    path.write_text(f"[{role.upper()}] {body}\n", encoding="utf-8")
    return path


async def _seed_run_messages(
    conn: asyncpg.Connection,
    *,
    run_id: UUID,
    session_id: UUID,
    base_at: datetime,
    slug: str,
) -> None:
    """Write the message → upload → text chain for the LLM transcript.

    For each (user, assistant) pair: messages_entry, uploads_entry
    with a real .txt on disk, text_uploads_entry, texts_entry,
    text_completion_entry, message_uploads_entry. This is what powers
    the per-run transcript view in the test detail page.
    """
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
        msg_at = base_at + timedelta(seconds=10 + turn_idx * 7)

        # Real file on disk
        file_path = _write_transcript_file(upload_id, role, body)
        size = file_path.stat().st_size

        await create_message(
            conn,
            run_id=run_id,
            role=role,
            id=msg_id,
        )
        await conn.execute(
            "UPDATE messages_entry SET created_at = $1 WHERE id = $2",
            msg_at,
            msg_id,
        )
        await create_upload(
            conn,
            session_id=session_id,
            file_path=str(file_path),
            mime_type="text/plain",
            size=size,
            id=upload_id,
        )
        await create_text(
            conn,
            session_id=session_id,
            id=text_id,
        )
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
    now: datetime,
    benchmark_invocations: list[tuple[UUID, UUID]],
    agent_ids: list[UUID],
    pricing_ids: list[UUID],
    profile_id: UUID,
) -> None:
    """Walk the canonical chain for one test."""
    if not benchmark_invocations:
        return
    if not agent_ids:
        return

    benchmark_id, _first_invocation = benchmark_invocations[
        test_idx % len(benchmark_invocations)
    ]
    # Use up to INVOCATIONS_PER_TEST template invocations under this benchmark.
    template_invocations = [
        inv for (b, inv) in benchmark_invocations if b == benchmark_id
    ][:INVOCATIONS_PER_TEST]

    base_offset = timedelta(days=test_idx * 3 + 1, hours=4)
    test_created_at = now - base_offset

    slug = f"tests-analytics/{test_idx}"
    test_id = sid(f"{slug}/test")
    test_call_id = sid(f"{slug}/test-call")
    test_run_id = sid(f"{slug}/test-run")
    group_id = sid(f"{slug}/group")
    group_name_id = sid(f"{slug}/group-name")
    session_id = profile_id  # session ties to profile in seed mode

    # 1. Group + name (test-level group for the dispatch context).
    await create_group(
        conn,
        session_id=session_id,
        artifact_type="test",
        id=group_id,
    )
    await create_group_name(
        conn,
        group_id=group_id,
        name=f"Benchmark test seed #{test_idx + 1}",
        session_id=session_id,
        id=group_name_id,
        generated=True,
    )

    # 2. test_entry — needs a call_id (test_entry FKs to calls_entry).
    # Create a parent run + call for the test row.
    await create_run(
        conn,
        group_id=group_id,
        session_id=session_id,
        id=test_run_id,
        agent_ids=[agent_ids[0]],
    )
    await create_call(
        conn,
        run_id=test_run_id,
        session_id=session_id,
        id=test_call_id,
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
    await conn.execute(
        "UPDATE test_entry SET created_at = $1, updated_at = $1 WHERE id = $2",
        test_created_at,
        test_id,
    )

    # 3. benchmark_test_entry — links test to benchmark.
    await create_benchmark_test(
        conn,
        benchmark_id=benchmark_id,
        test_id=test_id,
        session_id=session_id,
    )

    # 4. test_invocation_entry × N — one per template invocation.
    half_pricing = max(1, len(pricing_ids) // 2)
    input_pricing = pricing_ids[0] if pricing_ids else None
    output_pricing = (
        pricing_ids[half_pricing]
        if len(pricing_ids) > half_pricing
        else (pricing_ids[-1] if pricing_ids else None)
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

        inv_at = test_created_at + timedelta(minutes=5 + inv_idx * 8)

        # test_invocation needs its own run + call (test_invocation_entry
        # FKs to calls_entry via call_id).
        await create_run(
            conn,
            group_id=group_id,
            session_id=session_id,
            id=ti_run_id,
            agent_ids=[agent_for_inv],
        )
        await create_call(
            conn,
            run_id=ti_run_id,
            session_id=session_id,
            id=ti_call_id,
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
        await conn.execute(
            "UPDATE test_invocation_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            inv_at,
            ti_id,
        )

        # Run + tokens + pricing for the invocation's actual LLM work.
        # This is what drives Pricing dashboard rollups for tests.
        inp, out = _TOKEN_ENVELOPES[inv_idx % len(_TOKEN_ENVELOPES)]
        await create_token(
            conn,
            run_id=ti_run_id,
            session_id=session_id,
            id=sid(f"{inv_slug}/token"),
            input_tokens=inp,
            output_tokens=out,
        )
        if input_pricing is not None:
            await create_run_pricing_entry_internal(
                conn,
                session_id=session_id,
                pricing_type="input",
                run_id=ti_run_id,
                pricing_id=input_pricing,
                count=inp,
            )
        if output_pricing is not None:
            await create_run_pricing_entry_internal(
                conn,
                session_id=session_id,
                pricing_type="output",
                run_id=ti_run_id,
                pricing_id=output_pricing,
                count=out,
            )

        # LLM transcript chain (uploads → texts → message_uploads).
        # Real .txt files go on disk so the transcript view renders.
        await _seed_run_messages(
            conn,
            run_id=ti_run_id,
            session_id=session_id,
            base_at=inv_at,
            slug=inv_slug,
        )

        # trace + binding rows so the test-detail "history" tab has data.
        await create_test_invocation_traces(
            conn,
            test_invocation_id=ti_id,
            id=trace_id,
            run_id=ti_run_id,
        )
        await create_test_invocation_runs(
            conn,
            test_invocation_id=ti_id,
            id=binding_id,
            run_id=ti_run_id,
            test_invocation_traces_id=trace_id,
        )

        if completed:
            # completion + grade need their own call_ids (FKs to
            # calls_entry — same canonical pattern as the test row).
            for cid in (completion_call_id, grade_call_id):
                await create_call(
                    conn,
                    run_id=ti_run_id,
                    session_id=session_id,
                    id=cid,
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

            grade_at = inv_at + timedelta(minutes=8)
            await conn.execute(
                "UPDATE test_invocation_completion_entry SET created_at = $1, "
                "updated_at = $1 WHERE id = $2",
                grade_at,
                completion_id,
            )
            await conn.execute(
                "UPDATE test_grade_entry SET created_at = $1, updated_at = $1 "
                "WHERE id = $2",
                grade_at,
                grade_id,
            )


async def seed(pool: asyncpg.Pool, redis: Redis) -> None:
    """Entry point — fan out N tests across the available benchmarks."""
    _ = redis

    benchmark_invocations, agent_ids, pricing_ids, profile_id = (
        await _fetch_seed_inputs(pool)
    )

    if not benchmark_invocations or not agent_ids or profile_id is None:
        print(
            "  (skipped: need at least one benchmark + invocation, one agent, "
            "and one profile to seed tests)"
        )
        return

    now = datetime.now(timezone.utc)

    inserted = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for test_idx in range(TESTS_PER_RUN):
                try:
                    await _seed_one_test(
                        conn,
                        test_idx=test_idx,
                        now=now,
                        benchmark_invocations=benchmark_invocations,
                        agent_ids=agent_ids,
                        pricing_ids=pricing_ids,
                        profile_id=profile_id,
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  (test #{test_idx} skipped: {e})")
                    continue

    print(f"  OK: {inserted}/{TESTS_PER_RUN} tests seeded")
