"""Analytical seed — attempt history (Track A).

Inserts ~12 simulation attempts across the available
(persona × simulation × profile) cross-product so the dashboards have
real data on first load:

  • Activity / Reports / Leaderboard / Dashboard show non-empty rows.
  • Pricing rolls up real $/run by joining runs_entry → run_pricing.
  • Per-persona / per-simulation detail pages show attempt history.
  • Grade distribution looks plausible (35–95% range, ~10% failing).

Uses ONLY canonical entry create black-boxes from
``app/tools/entries/<x>/create.py`` — no inline SQL. Discovers
available personas / scenarios / profiles / agents at runtime and
threads them through the canonical chain:

  attempt → attempt_chat (pointing at the simulation's pre-seeded
  chat_entry) → attempt_chat_bridge → groups + group_names →
  N × (attempt_message + attempt_content with text inline) →
  attempt_chat_completion + attempt_completion + attempt_grade
  (when completed) → runs + tokens + run_pricing (drives Pricing).

Determinism:
  • All ids via sid("attempts-analytics/<slug>"), so reseeding gives
    stable ids — no UUID drift across builds.
  • created_at is anchored to now() with deterministic offsets per
    attempt index, so the time-spread is reproducible per build.
  • Message bodies + scores derive from (sim_idx, persona_idx) — no
    random() calls.
"""

from __future__ import annotations

import asyncpg
from datetime import datetime, timedelta, timezone
from redis.asyncio import Redis
from uuid import UUID

from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import create_attempt_chat_bridge
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)
from app.tools.entries.attempt_completion.create import create_attempt_completion
from app.tools.entries.attempt_content.create import create_attempt_content
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.tokens.create import create_token

from database.seeds.ids import sid


ATTEMPT_COUNT = 12
TURNS_PER_ATTEMPT = 6  # alternating user / persona
COMPLETED_RATIO = 0.7  # 70% of attempts have a grade
RUNS_PER_ATTEMPT = 3   # agent dispatches per attempt (drives Pricing/Leaderboard)


# Per-(persona_idx, turn_idx) deterministic lines. The attempt seed
# loops over these rather than calling random() so re-seed produces
# identical content. Pulled to module top so the corpus is auditable.
_USER_LINES = [
    "Hi, can you help me with the assignment from last week?",
    "I'm not sure how to approach this — what would you recommend?",
    "Thanks, that helps. What about the second part?",
    "Got it. Should I focus on the analytical or the creative angle first?",
    "Could you give me an example of what a good answer looks like?",
    "OK I think I understand now. Let me try drafting something.",
]

_PERSONA_LINES = [
    "Of course — let's walk through it together. What part is giving you trouble?",
    "I'd start by breaking the problem into smaller pieces. What's the first thing you'd check?",
    "The second part builds on the first, so once you have that down it should click.",
    "Either is fine, but I think starting analytical gives you a clearer foundation.",
    "Sure — imagine you're explaining it to someone who's never seen it. That tends to surface gaps.",
    "Sounds good. Send the draft when you're ready and I'll point out anything to tighten up.",
]


# Per-attempt grade scores — deterministic distribution covering
# the desired 35–95% range with one failing (32) for variety.
_SCORES = [88, 76, 92, 65, 81, 73, 95, 58, 84, 32, 71, 89]
_TIME_TAKEN_SECONDS = [780, 1240, 540, 980, 1430, 720, 460, 1820, 690, 920, 1350, 600]


# Synthetic token envelopes per agent (model-agnostic — just plausible
# input/output ranges that produce reasonable cost when joined to
# pricing). Indexed by (run_idx mod 3) for variety.
_TOKEN_ENVELOPES = [
    (1850, 720),   # heavy input, modest output
    (1200, 1100),  # balanced
    (640, 380),    # short turn
]


async def _fetch_seed_inputs(
    pool: asyncpg.Pool,
) -> tuple[list[UUID], list[UUID], list[UUID], list[UUID], list[UUID], dict[UUID, UUID]]:
    """Discover available personas / scenario chats / profiles / agents
    / pricings in the DB. Returns deterministic-ordered id lists so
    the seed picks the same items on every run.

    Returns:
        (
            persona_ids,
            chat_ids_with_simulation,
            profile_ids,
            agent_ids,
            pricing_ids,
            scenario_chat_to_persona,  # chat_id → primary scenario persona_id
        )
    """
    async with pool.acquire() as conn:
        personas = await conn.fetch(
            "SELECT id FROM personas_entry WHERE active=true ORDER BY created_at"
        )
        # Pre-seeded chat_entry rows — one per scenario.
        chats = await conn.fetch(
            "SELECT id FROM chat_entry WHERE active=true ORDER BY created_at"
        )
        profiles = await conn.fetch(
            "SELECT id FROM profiles_resource WHERE active=true ORDER BY created_at"
        )
        agents = await conn.fetch(
            "SELECT id FROM agents_resource WHERE active=true ORDER BY created_at LIMIT 6"
        )
        pricings = await conn.fetch(
            "SELECT id FROM pricing_resource WHERE active=true "
            "AND pricing_type IN ('input', 'output') ORDER BY pricing_type, created_at "
            "LIMIT 6"
        )
        # Best-effort scenario→persona mapping for assistant-voice
        # content. attempt_content.persona_id stores which voice the
        # turn came from; user turns use the user_persona_id, persona
        # turns use the scenario's persona.
        scenario_chat_to_persona: dict[UUID, UUID] = {}
        try:
            chat_persona_rows = await conn.fetch(
                """
                SELECT cspc.chat_id, cspc.personas_id
                FROM chat_simulations_personas_connection cspc
                WHERE cspc.active = true
                """
            )
            for r in chat_persona_rows:
                scenario_chat_to_persona.setdefault(r["chat_id"], r["personas_id"])
        except Exception:
            # Connection table name may differ across schemas; fall
            # back to using user_persona_id for both voices.
            scenario_chat_to_persona = {}

    return (
        [r["id"] for r in personas],
        [r["id"] for r in chats],
        [r["id"] for r in profiles],
        [r["id"] for r in agents],
        [r["id"] for r in pricings],
        scenario_chat_to_persona,
    )


async def _seed_one_attempt(
    conn: asyncpg.Connection,
    *,
    idx: int,
    now: datetime,
    user_persona_id: UUID,
    chat_id: UUID,
    profile_id: UUID,
    agent_id: UUID | None,
    input_pricing_id: UUID | None,
    output_pricing_id: UUID | None,
    sim_persona_id: UUID | None,
) -> None:
    """Walk the canonical chain for one attempt.

    Time anchoring: each attempt sits ``idx + 1`` days back from now,
    spread across the last ATTEMPT_COUNT days. Newest attempt is at
    idx=0 (yesterday); oldest at idx=11 (12 days ago).
    """
    base_offset = timedelta(days=idx + 1, hours=(idx * 3) % 24)
    attempt_created_at = now - base_offset

    completed = idx < int(ATTEMPT_COUNT * COMPLETED_RATIO)

    slug = f"attempts-analytics/{idx}"
    attempt_id = sid(f"{slug}/attempt")
    attempt_chat_id = sid(f"{slug}/attempt-chat")
    group_id = sid(f"{slug}/group")
    group_name_id = sid(f"{slug}/group-name")

    # Pull profiles_id (resource) — for analytics we treat profile_id
    # and profiles_id as the same since profiles_resource is the
    # snapshot of profiles_entry. attempt.create needs profiles_id.
    profiles_id_for_attempt = profile_id

    # Use the simulation's persona for the assistant voice when
    # available; fall back to user persona so attempt_content always
    # FKs to a valid personas_entry row.
    voice_persona_id = sim_persona_id or user_persona_id

    session_id_for_attempt = profile_id  # session ties to profile in seed mode

    # 1. groups + group_names (the agent dispatch context for this attempt)
    await create_group(
        conn,
        session_id=session_id_for_attempt,
        artifact_type="attempt",
        id=group_id,
    )
    await create_group_name(
        conn,
        group_id=group_id,
        name=f"Attempt seed #{idx + 1}",
        session_id=session_id_for_attempt,
        id=group_name_id,
        generated=True,
    )

    # 2. attempt_entry (also writes attempt_profiles_connection inside)
    await create_attempt(
        conn,
        session_id=session_id_for_attempt,
        user_persona_id=user_persona_id,
        profiles_id=profiles_id_for_attempt,
        id=attempt_id,
        name=f"Practice attempt #{idx + 1}",
        description="Seeded attempt for analytics dashboards",
        practice=False,
        num_chats=1,
    )

    # Patch the attempt's created_at so the time spread is real (the
    # canonical create uses now() default; we want our deterministic
    # offset to drive analytics date filters).
    await conn.execute(
        "UPDATE attempt_entry SET created_at = $1, updated_at = $1 WHERE id = $2",
        attempt_created_at,
        attempt_id,
    )

    # 3. attempt_chat_entry — bound to the simulation's pre-seeded chat.
    await create_attempt_chat(
        conn,
        session_id=session_id_for_attempt,
        chat_id=chat_id,
        id=attempt_chat_id,
        title=f"Session {idx + 1}",
        position=0,
        text_enabled=True,
        audio_enabled=False,
        hints_enabled=True,
        show_objectives=True,
    )
    await conn.execute(
        "UPDATE attempt_chat_entry SET created_at = $1, updated_at = $1 WHERE id = $2",
        attempt_created_at,
        attempt_chat_id,
    )

    # 4. bridge: attempt ↔ attempt_chat
    await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt_id,
        attempt_chat_id=attempt_chat_id,
        session_id=session_id_for_attempt,
    )

    # 5. attempt_message + attempt_content — the visible conversation.
    # Alternating user (idx even) / persona (idx odd) turns. Each
    # message gets a content row with the inline body and the right
    # persona_id (whose voice).
    for t in range(TURNS_PER_ATTEMPT):
        is_user_turn = t % 2 == 0
        turn_persona = user_persona_id if is_user_turn else voice_persona_id
        line = (_USER_LINES if is_user_turn else _PERSONA_LINES)[t % len(_USER_LINES)]
        msg_id = sid(f"{slug}/msg/{t}")
        content_id = sid(f"{slug}/content/{t}")
        msg_at = attempt_created_at + timedelta(minutes=2 + t * 2)

        await create_attempt_message(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id_for_attempt,
            id=msg_id,
        )
        await conn.execute(
            "UPDATE attempt_message_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            msg_at,
            msg_id,
        )
        await create_attempt_content(
            conn,
            message_id=msg_id,
            session_id=session_id_for_attempt,
            content=line,
            persona_id=turn_persona,
            id=content_id,
        )
        await conn.execute(
            "UPDATE attempt_content_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            msg_at,
            content_id,
        )

    # 6. Agent activity rows — runs + tokens + run_pricing. These
    # power Pricing dashboard cost rollups, Leaderboard token usage,
    # Activity timestamps. Skipped for in-progress attempts to give
    # the analytics views some "no agent activity yet" rows.
    if completed and agent_id is not None:
        for r in range(RUNS_PER_ATTEMPT):
            run_id = sid(f"{slug}/run/{r}")
            run_at = attempt_created_at + timedelta(minutes=4 + r * 2)
            await create_run(
                conn,
                group_id=group_id,
                session_id=session_id_for_attempt,
                id=run_id,
                agent_ids=[agent_id],
            )
            await conn.execute(
                "UPDATE runs_entry SET created_at = $1 WHERE id = $2",
                run_at,
                run_id,
            )

            inp_tokens, out_tokens = _TOKEN_ENVELOPES[r % len(_TOKEN_ENVELOPES)]
            token_id = sid(f"{slug}/token/{r}")
            await create_token(
                conn,
                run_id=run_id,
                session_id=session_id_for_attempt,
                id=token_id,
                input_tokens=inp_tokens,
                output_tokens=out_tokens,
            )
            await conn.execute(
                "UPDATE tokens_entry SET created_at = $1 WHERE id = $2",
                run_at,
                token_id,
            )

            # Pricing rows — one input + one output, joined to the
            # actual pricing_resource ids we discovered. Drives the
            # cost rollup on the Pricing dashboard.
            if input_pricing_id is not None:
                pi_id = sid(f"{slug}/pricing/{r}/input")
                await create_run_pricing_entry_internal(
                    conn,
                    session_id=session_id_for_attempt,
                    pricing_type="input",
                    run_id=run_id,
                    pricing_id=input_pricing_id,
                    count=inp_tokens,
                )
                await conn.execute(
                    "UPDATE run_pricing_entry SET created_at = $1 WHERE id = $2",
                    run_at,
                    pi_id,
                )
            if output_pricing_id is not None:
                po_id = sid(f"{slug}/pricing/{r}/output")
                await create_run_pricing_entry_internal(
                    conn,
                    session_id=session_id_for_attempt,
                    pricing_type="output",
                    run_id=run_id,
                    pricing_id=output_pricing_id,
                    count=out_tokens,
                )
                await conn.execute(
                    "UPDATE run_pricing_entry SET created_at = $1 WHERE id = $2",
                    run_at,
                    po_id,
                )

    # 7. Completions + grade — only for the completed slice. The
    # in-progress attempts are intentionally left without a grade so
    # the dashboards show "in_progress" rows alongside completed.
    if completed:
        chat_completion_id = sid(f"{slug}/chat-completion")
        await create_attempt_chat_completion(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id_for_attempt,
            id=chat_completion_id,
            stop=True,
        )

        completion_id = sid(f"{slug}/completion")
        await create_attempt_completion(
            conn,
            attempt_id=attempt_id,
            session_id=session_id_for_attempt,
            id=completion_id,
            stop=True,
        )

        grade_id = sid(f"{slug}/grade")
        score = _SCORES[idx % len(_SCORES)]
        time_taken = _TIME_TAKEN_SECONDS[idx % len(_TIME_TAKEN_SECONDS)]
        await create_attempt_grade(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id_for_attempt,
            time_taken=time_taken,
            passed=score >= 60,
            score=score,
            id=grade_id,
        )

        # Stamp completion timestamps so analytics dashboards (which
        # filter by completion date) see realistic dates.
        completion_at = attempt_created_at + timedelta(minutes=15 + idx)
        await conn.execute(
            "UPDATE attempt_chat_completion_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            completion_at,
            chat_completion_id,
        )
        await conn.execute(
            "UPDATE attempt_completion_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            completion_at,
            completion_id,
        )
        await conn.execute(
            "UPDATE attempt_grade_entry SET created_at = $1, updated_at = $1 "
            "WHERE id = $2",
            completion_at,
            grade_id,
        )


async def seed(pool: asyncpg.Pool, redis: Redis) -> None:
    """Entry point — discover available FK targets, fan out N attempts.

    Idempotent: deterministic sids mean re-running this seed reuses
    existing rows. The UPDATE statements for created_at always run,
    so re-seeding shifts timestamps forward to "now" — which is what
    we want for demo dashboards.
    """
    _ = redis  # not currently used; kept on the signature for future caching needs

    (
        persona_ids,
        chat_ids,
        profile_ids,
        agent_ids,
        pricing_ids,
        scenario_chat_to_persona,
    ) = await _fetch_seed_inputs(pool)

    if not persona_ids or not chat_ids or not profile_ids:
        print(
            "  (skipped: need at least one persona, chat, and profile to seed attempts)"
        )
        return

    now = datetime.now(timezone.utc)
    primary_agent = agent_ids[0] if agent_ids else None
    # pricing_resource has separate input/output rows; pick first of each.
    input_pricing = next(
        (
            pid
            for pid in pricing_ids
            # We can't tell pricing_type from the id list cheaply here;
            # the SQL above ordered by pricing_type so input comes first.
        ),
        None,
    )
    # Cheap split: first half input, second half output (matches the
    # ORDER BY pricing_type in the fetch).
    half = max(1, len(pricing_ids) // 2)
    input_pricing = pricing_ids[0] if pricing_ids else None
    output_pricing = pricing_ids[half] if len(pricing_ids) > half else (
        pricing_ids[-1] if pricing_ids else None
    )

    inserted = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx in range(ATTEMPT_COUNT):
                user_persona_id = persona_ids[idx % len(persona_ids)]
                chat_id = chat_ids[idx % len(chat_ids)]
                profile_id = profile_ids[idx % len(profile_ids)]
                sim_persona_id = scenario_chat_to_persona.get(chat_id)

                try:
                    await _seed_one_attempt(
                        conn,
                        idx=idx,
                        now=now,
                        user_persona_id=user_persona_id,
                        chat_id=chat_id,
                        profile_id=profile_id,
                        agent_id=primary_agent,
                        input_pricing_id=input_pricing,
                        output_pricing_id=output_pricing,
                        sim_persona_id=sim_persona_id,
                    )
                    inserted += 1
                except Exception as e:
                    # Don't abort the whole seed for one bad row —
                    # log + continue. Common cause: FK target missing
                    # in this setup (e.g., setup has no scenarios).
                    print(f"  (attempt #{idx} skipped: {e})")
                    continue

    print(f"  OK: {inserted}/{ATTEMPT_COUNT} attempts seeded")
