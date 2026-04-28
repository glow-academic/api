"""Analytical seed — attempt history (Track A).

Inserts ~12 simulation attempts so the dashboards (Activity, Reports,
Pricing, Leaderboard, Dashboard, per-Persona/Simulation pages) have
data on first load.

**Canonical-only**: this seed uses ONLY the black-box functions in
``app/tools/resources/<x>/search.py`` and
``app/tools/entries/<x>/create.py``. No inline SELECT or UPDATE — and
in particular no ``UPDATE ... SET created_at = ...`` hacks. As a
trade-off, every row lands at ``now()`` because the canonical create
functions don't currently accept a ``created_at`` override; if/when
they do, this seed should pass per-attempt offsets to spread the
timeline. For now the demo time distribution is "all today".

Runner ordering: this runs AFTER cohorts + benchmark sync as part
of "Phase 3 — analytical seeds". By that point everything we need
is in place: ``profile_personas_resource`` rows wire profiles to
their assigned personas (the canonical ``user_persona_id`` source),
``chat_entry`` rows exist (one per scenario), ``agents_resource`` /
``pricing_resource`` are populated by the platform module, and
``personas_resource`` has the persona templates we wrap into
``personas_entry`` via the canonical ``create_personas`` black-box.

Chain per attempt:
  groups + group_names → attempt → attempt_chat (pointing at the
  simulation's pre-seeded chat_entry) → attempt_chat_bridge →
  N × (attempt_message + attempt_content with text inline) →
  (when completed) attempt_chat_completion + attempt_completion +
  attempt_grade → (when has agent activity) runs + tokens +
  run_pricing (drives Pricing dashboard).

Determinism: all ids via ``sid("attempts-analytics/...")``. Re-running
the seed is idempotent on canonical creates (entries with the same
UUID short-circuit at the DB layer).
"""

from __future__ import annotations

import asyncpg
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
from app.tools.entries.chat.search import search_chat_entries_internal
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.personas.create import create_personas
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.tokens.create import create_token
from app.tools.resources.agents.search import search_agents
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.profile_personas.search import search_profile_personas

from database.seeds.ids import sid


ATTEMPT_COUNT = 12
TURNS_PER_ATTEMPT = 6
COMPLETED_RATIO = 0.7
RUNS_PER_ATTEMPT = 3


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


_SCORES = [88, 76, 92, 65, 81, 73, 95, 58, 84, 32, 71, 89]
_TIME_TAKEN_SECONDS = [780, 1240, 540, 980, 1430, 720, 460, 1820, 690, 920, 1350, 600]
_TOKEN_ENVELOPES = [(1850, 720), (1200, 1100), (640, 380)]


async def _wrap_personas_resource(
    conn: asyncpg.Connection, resource_ids: list[UUID]
) -> dict[UUID, UUID]:
    """For each persona resource id, create a personas_entry that wraps
    it. Returns {resource_id → entry_id}.

    ``attempt_entry.user_persona_id`` and ``attempt_content.persona_id``
    both FK to ``personas_entry``. The seed-time persona templates
    live in ``personas_resource`` — the canonical bridge is
    ``create_personas(persona_ids=[resource_id])`` which inserts the
    entry plus the ``personas_personas_connection`` link in one shot.
    """
    mapping: dict[UUID, UUID] = {}
    for idx, rid in enumerate(resource_ids):
        entry_id = sid(f"attempts-analytics/persona-entry/{idx}")
        await create_personas(conn, id=entry_id, persona_ids=[rid])
        mapping[rid] = entry_id
    return mapping


async def _seed_one_attempt(
    conn: asyncpg.Connection,
    *,
    idx: int,
    user_persona_entry_id: UUID,
    chat_id: UUID,
    profile_id: UUID,
    voice_persona_entry_id: UUID,
    agent_id: UUID | None,
    input_pricing_id: UUID | None,
    output_pricing_id: UUID | None,
) -> None:
    """Walk the canonical chain for one attempt. All rows are stamped
    at now() — the canonical creates don't currently accept created_at
    overrides, and this seed deliberately avoids inline UPDATEs."""
    completed = idx < int(ATTEMPT_COUNT * COMPLETED_RATIO)

    slug = f"attempts-analytics/{idx}"
    attempt_id = sid(f"{slug}/attempt")
    attempt_chat_id = sid(f"{slug}/attempt-chat")
    group_id = sid(f"{slug}/group")
    group_name_id = sid(f"{slug}/group-name")
    session_id = profile_id

    # 1. Group + group_name (the agent-dispatch context).
    await create_group(
        conn,
        session_id=session_id,
        artifact_type="attempt",
        id=group_id,
    )
    await create_group_name(
        conn,
        group_id=group_id,
        name=f"Attempt seed #{idx + 1}",
        session_id=session_id,
        id=group_name_id,
        generated=True,
    )

    # 2. attempt_entry (writes attempt_profiles_connection inside).
    await create_attempt(
        conn,
        session_id=session_id,
        user_persona_id=user_persona_entry_id,
        profiles_id=profile_id,
        id=attempt_id,
        name=f"Practice attempt #{idx + 1}",
        description="Seeded attempt for analytics dashboards",
        practice=False,
        num_chats=1,
    )

    # 3. attempt_chat_entry pointing at the simulation's pre-seeded chat.
    await create_attempt_chat(
        conn,
        session_id=session_id,
        chat_id=chat_id,
        id=attempt_chat_id,
        title=f"Session {idx + 1}",
        position=0,
        text_enabled=True,
        audio_enabled=False,
        hints_enabled=True,
        show_objectives=True,
    )

    # 4. attempt ↔ attempt_chat bridge.
    await create_attempt_chat_bridge(
        conn,
        attempt_id=attempt_id,
        attempt_chat_id=attempt_chat_id,
        session_id=session_id,
    )

    # 5. The visible conversation — alternating user / persona turns.
    for t in range(TURNS_PER_ATTEMPT):
        is_user_turn = t % 2 == 0
        turn_persona_entry = (
            user_persona_entry_id if is_user_turn else voice_persona_entry_id
        )
        line = (_USER_LINES if is_user_turn else _PERSONA_LINES)[t % len(_USER_LINES)]
        msg_id = sid(f"{slug}/msg/{t}")
        content_id = sid(f"{slug}/content/{t}")

        await create_attempt_message(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id,
            id=msg_id,
        )
        await create_attempt_content(
            conn,
            message_id=msg_id,
            session_id=session_id,
            content=line,
            persona_id=turn_persona_entry,
            id=content_id,
        )

    # 6. Agent activity — runs + tokens + run_pricing. Drives Pricing
    # dashboard cost rollups when joined to pricing_resource. Skipped
    # for in-progress attempts so dashboards see "no agent activity"
    # rows alongside the active ones.
    if completed and agent_id is not None:
        for r in range(RUNS_PER_ATTEMPT):
            run_id = sid(f"{slug}/run/{r}")
            await create_run(
                conn,
                group_id=group_id,
                session_id=session_id,
                id=run_id,
                agent_ids=[agent_id],
            )
            inp_tokens, out_tokens = _TOKEN_ENVELOPES[r % len(_TOKEN_ENVELOPES)]
            await create_token(
                conn,
                run_id=run_id,
                session_id=session_id,
                id=sid(f"{slug}/token/{r}"),
                input_tokens=inp_tokens,
                output_tokens=out_tokens,
            )
            if input_pricing_id is not None:
                await create_run_pricing_entry_internal(
                    conn,
                    session_id=session_id,
                    pricing_type="input",
                    run_id=run_id,
                    pricing_id=input_pricing_id,
                    count=inp_tokens,
                )
            if output_pricing_id is not None:
                await create_run_pricing_entry_internal(
                    conn,
                    session_id=session_id,
                    pricing_type="output",
                    run_id=run_id,
                    pricing_id=output_pricing_id,
                    count=out_tokens,
                )

    # 7. Completions + grade — only for the completed slice.
    if completed:
        await create_attempt_chat_completion(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id,
            id=sid(f"{slug}/chat-completion"),
            stop=True,
        )
        await create_attempt_completion(
            conn,
            attempt_id=attempt_id,
            session_id=session_id,
            id=sid(f"{slug}/completion"),
            stop=True,
        )
        score = _SCORES[idx % len(_SCORES)]
        time_taken = _TIME_TAKEN_SECONDS[idx % len(_TIME_TAKEN_SECONDS)]
        await create_attempt_grade(
            conn,
            chat_id=attempt_chat_id,
            session_id=session_id,
            time_taken=time_taken,
            passed=score >= 60,
            score=score,
            id=sid(f"{slug}/grade"),
        )


async def seed(pool: asyncpg.Pool, redis: Redis) -> None:
    """Entry point — discover available FK targets via canonical search,
    fan out N attempts. No inline SQL anywhere — only black-boxes.
    """
    inserted = 0
    async with pool.acquire() as conn:
        # ── Discovery via canonical search black-boxes ─────────────
        # MVs are refreshed by the runner before this seed runs (see
        # runner.py "Phase 3 — Analytical seeds" block); we don't
        # need to call refresh_* helpers here.
        # profile_personas_resource is the canonical "this profile
        # plays as this persona" assignment table — exactly what the
        # cohort seed phase populates and what `attempt.user_persona_id`
        # mirrors at runtime. We pull the (profile, persona_resource)
        # pairs from there. bypass_cache=True because the seed-gen
        # container's Redis is fresh and stale cache entries shouldn't
        # exist anyway.
        profile_personas = await search_profile_personas(
            conn, redis, limit_count=50, bypass_cache=True
        )
        # Available scenario chats — pre-seeded by the simulation seeds.
        chats = await search_chat_entries_internal(conn, limit_count=50)
        # Agents + pricing for the agent-activity chain.
        agents = await search_agents(conn, redis, limit_count=6, bypass_cache=True)
        input_pricings = await search_pricing(
            conn, redis, pricing_type="input", limit_count=4, bypass_cache=True
        )
        output_pricings = await search_pricing(
            conn, redis, pricing_type="output", limit_count=4, bypass_cache=True
        )
        print(
            f"  (discovery: profile_personas={len(profile_personas)}, "
            f"chats={len(chats)}, agents={len(agents)}, "
            f"input_pricings={len(input_pricings)}, "
            f"output_pricings={len(output_pricings)})"
        )

        if not profile_personas or not chats:
            print(
                "  (skipped: need at least one profile_personas and "
                "one chat_entry to seed attempts)"
            )
            return

        # Wrap every persona_resource we'll touch in a personas_entry
        # via the canonical create_personas. attempt_entry.user_persona_id
        # and attempt_content.persona_id both FK to personas_entry, so
        # this conversion is required.
        unique_persona_resource_ids = list(
            {pp.persona_id for pp in profile_personas}
        )
        persona_resource_to_entry = await _wrap_personas_resource(
            conn, unique_persona_resource_ids
        )

        primary_agent_id = agents[0].id if agents else None
        input_pricing_id = input_pricings[0].id if input_pricings else None
        output_pricing_id = output_pricings[0].id if output_pricings else None

        async with conn.transaction():
            for idx in range(ATTEMPT_COUNT):
                pp = profile_personas[idx % len(profile_personas)]
                chat = chats[idx % len(chats)]
                # search_chat_entries_internal returns list[dict] from
                # chat_mv (the MV column is `chat_entry_id`).
                chat_id = chat["chat_entry_id"]

                user_persona_entry = persona_resource_to_entry.get(pp.persona_id)
                if user_persona_entry is None:
                    print(f"  (attempt #{idx} skipped: persona entry not wrapped)")
                    continue

                # The "voice" persona for assistant turns is the same
                # persona_entry as the user persona for now — the
                # canonical chat_personas_connection lookup would give
                # the scenario-specific persona, but doing that here
                # would re-introduce a SELECT we'd have to query
                # outside a black-box. Acceptable simplification: both
                # voices share a personas_entry; persona_id field on
                # attempt_content still resolves correctly, just to a
                # less-distinct voice. Future enhancement: add
                # search_chat_personas to the canonical surface.
                voice_persona_entry = user_persona_entry

                try:
                    await _seed_one_attempt(
                        conn,
                        idx=idx,
                        user_persona_entry_id=user_persona_entry,
                        chat_id=chat_id,
                        profile_id=pp.profile_id,
                        voice_persona_entry_id=voice_persona_entry,
                        agent_id=primary_agent_id,
                        input_pricing_id=input_pricing_id,
                        output_pricing_id=output_pricing_id,
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  (attempt #{idx} skipped: {e})")
                    continue

    print(f"  OK: {inserted}/{ATTEMPT_COUNT} attempts seeded")
