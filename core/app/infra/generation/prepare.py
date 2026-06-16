"""Generation prepare — deterministic infra function.

Creates all DB state needed for execution:
  1. resolve_websocket_context → agents, tools, prompts, models
  2. Enrich tools (args, args_outputs, permissions, instruction templates)
  3. Build agent groups from scores
  4. create_run (active=not soft, linked to agents)
  5. persist_run_message — system, developer, user messages
  6. setup_generation_test — test + invocations if rubrics
  7. Returns PrepareGenerationResult with agent dispatches
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import asyncpg

from app.infra.generation import convert_tools_to_dict
from app.infra.generation.types import (
    AgentDispatch,
    PrepareGenerationResult,
)
from app.infra.types import ArtifactRequest
from app.infra.websocket.generation_types import GeneratePayload
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.setup_generation_test import (
    AgentTestConfig,
    setup_generation_test,
)
from app.infra.websocket_context import resolve_websocket_context
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def _resolve_modality_pair(
    *,
    modalities: list[str] | None,
    audios_id: str | None,
    conversation_id: str | None,
) -> tuple[set[str], set[str]]:
    """Resolve **dispatch-side** (input, output) modalities for an executor.

    NOTE: this is the DISPATCH vocabulary, not the model vocabulary.
    It produces the synthetic ``audio_stream`` marker so
    ``infra.generation.dispatch.resolve_executor`` can distinguish a live
    realtime session (``audio_stream`` in inputs + ``audio`` in outputs →
    "realtime" executor) from a one-shot audio request (``audio`` in
    inputs → "stt" executor). No model declares ``audio_stream`` as a
    modality; agent SELECTION uses the model-level set
    ``{text, audio, image, video, call}`` directly (see the
    ``selection_in_mods`` / ``score_agents`` block in
    ``prepare_generation``).

    Inputs are inferred from the request payload:
      - conversation_id present → ``audio_stream`` (live streaming)
      - audios_id present → ``audio`` (one-shot)
      - otherwise → ``text``

    Outputs come directly from the client-declared modalities list, with a
    sensible default of {text, call} when omitted so the agentic text loop
    remains the default behavior and tool calls are always allowed.
    """
    if conversation_id:
        input_set = {"audio_stream"}
    elif audios_id:
        input_set = {"audio"}
    else:
        input_set = {"text"}

    output_set = set(modalities) if modalities else {"text", "call"}
    return input_set, output_set


from app.infra.server_timing import timed
from app.utils.cache.hedged_row import transaction_with_writeback


async def prepare_generation(
    pool: asyncpg.Pool,
    redis: Any,
    *,
    profile_id: UUID,
    profiles_id: UUID,
    session_id: UUID,
    group_id: UUID,
    artifact_type: str,
    artifact_config: Any,
    payload: GeneratePayload,
    soft: bool = False,
) -> PrepareGenerationResult:
    """Resolve context, create run, build agent dispatches, persist messages.

    Returns PrepareGenerationResult with all dispatches ready for execution.

    When soft=True, run is created with active=false — everything is set up
    but nothing executes until accepted.
    """
    from app.infra.tool_graph import score_agents
    from fastapi import HTTPException
    from app.infra.websocket.prepare_pipeline import (
        build_agent_dispatch,
        enrich_tools_with_args,
        enrich_tools_with_args_outputs,
        enrich_tools_with_instruction_templates,
        enrich_tools_with_permissions,
        resolve_agent_config,
        validate_payload,
    )
    from app.tools.entries.runs.create import create_run

    # --- Step 1: Validate ---
    resource_types = list(artifact_config.valid_resource_types)
    payload_params = payload.params or {}

    draft_id = payload_params.get("draft_id")
    error = validate_payload(
        artifact_type=artifact_type,
        requires_draft=artifact_config.requires_draft,
        draft_id=draft_id,
    )
    if error:
        raise ValueError(error)

    # --- Step 2: Resolve artifact_id ---
    artifact_id = payload_params.get("artifact_id")
    payload_metadata = payload.metadata or {}
    if artifact_type == "profile" and not artifact_id and payload_metadata.get("staff_id"):
        artifact_id = uuid.UUID(payload_metadata["staff_id"])

    # --- Step 3: Resolve context ---
    # Thread modalities to filter systems by capability
    requested_modalities = payload.modalities

    with timed("prepare"):
        ws_ctx = await resolve_websocket_context(
            pool,
            redis,
            profile_id=profile_id,
            requests=[
                ArtifactRequest(
                    artifact_type=artifact_type,
                    artifact_id=artifact_id,
                    group_id=group_id,
                    draft_id=draft_id,
                )
            ],
            modalities=requested_modalities,
            bypass_cache=True,
        )

    if ws_ctx is None:
        raise ValueError("Failed to resolve context.")

    if not ws_ctx.agents:
        raise ValueError("No system/agent configuration found.")

    # Lookups from ws_ctx
    agents_by_id = {a.id: a for a in ws_ctx.agents}
    models_by_id = {m.id: m for m in ws_ctx.models}
    providers_by_id = {p.id: p for p in ws_ctx.providers}
    config_agents = ws_ctx.agents

    # --- Trace-driven canonical agent (faithful replay) ---
    # When `params.trace_id` is set we're replaying a historical run.
    # The dispatch agent must be the test_invocation's agent (the one
    # under test) — NOT whatever score_tools picks for the test
    # artifact (which would win the test orchestrator agent and run
    # against its tools/prompt instead of the historical setup).
    #
    # The trace's bundle (prompt_ids/tool_ids/instruction_ids) layers
    # on top as per-turn overrides. They came from the picker, which
    # copied them off the historical run's agent — so by default the
    # synth equals the historical agent. Future per-turn customization
    # (e.g. user-typed prompt) flows through the same override slot.
    #
    # After this block, score_agents is skipped: agent_groups is
    # already set, ws_ctx-derived lookups are augmented with the
    # synth agent + its resources.
    #
    # ── Side-effect safety on replay ───────────────────────────────
    # Replays must NOT mutate live state. The system already
    # guarantees this via the canonical soft-write pattern:
    #
    #   1. GeneratePayload.dangerous defaults to False.
    #   2. run_from_payload sets tool_soft = not payload.dangerous = True.
    #   3. execute.py constructs InfraContext(soft=True, accept=None).
    #   4. execute_infra_operation honors soft+accept on every write
    #      impl; reads pass through normally.
    #   5. accept=None leaves dormant records dormant forever — the
    #      canonical "draft pending acceptance" state, not garbage.
    #
    # No dry_run flag, no test.* event remapping, no atomic cleanup
    # logic needed. The dispatch loop produces the right behavior
    # for free as long as nobody flips dangerous=True on a trace
    # generate (a defensive guard here is a future refinement).
    #
    # ── Why no replay tape ─────────────────────────────────────────
    # Earlier iterations pre-loaded historical tool outputs and served
    # them back at dispatch time, keyed by ``(artifact, operation)``.
    # That was incorrect: it ignored the LLM's actual arguments, so a
    # benchmark of a *new* prompt got tool responses tailored to the
    # *original* prompt's questions — measurement was meaningless.
    # We now dispatch live with ``soft=True`` (the default for
    # trace-driven runs via ``not payload.dangerous``). Reads return
    # current state; writes stage dormant ``soft_calls_entry`` rows
    # tagged ``eval=true`` so the UI's pending surfaces filter them
    # out. The tradeoff is non-historical responses for evolving data;
    # the win is honest benchmarks.
    trace_dispatch_agent: Any = None
    eval_run = False
    trace_id_param = payload_params.get("trace_id")
    if trace_id_param:
        from app.infra.test.trace_context import resolve_trace_context
        from app.tools.entries.test_invocation.get import get_test_invocations
        from app.tools.resources.agents.get import get_agents
        from app.tools.resources.instructions.get import get_instructions
        from app.tools.resources.prompts.get import get_prompts
        from app.tools.resources.tools.get import get_tools

        eval_run = True
        trace_uuid = (
            trace_id_param
            if isinstance(trace_id_param, uuid.UUID)
            else uuid.UUID(str(trace_id_param))
        )
        async with pool.acquire() as conn:
            trace_ctx = await resolve_trace_context(conn, trace_uuid)
            invs = await get_test_invocations(
                conn, [trace_ctx.test_invocation_id], redis,
            )
        if not invs:
            raise ValueError(
                f"trace replay: parent invocation {trace_ctx.test_invocation_id} not found"
            )
        inv_for_trace = invs[0]

        if inv_for_trace.agent_ids:
            # Load the canonical agent the test_invocation was set up
            # with (model + provider + key + voice + temperature etc.
            # all live on the agent_resource).
            base_agents = await get_agents(
                pool, list(inv_for_trace.agent_ids[:1]), redis, bypass_cache=True
            )
            if base_agents:
                base_agent = base_agents[0]
                # Layer trace bundle overrides on top of the canonical
                # agent. Empty trace fields fall through to the agent's
                # own values — so this is also correct when the picker
                # copied the agent's bundle verbatim (trace == agent).
                override_fields: dict[str, Any] = {}
                if trace_ctx.prompt_ids:
                    override_fields["prompt_id"] = trace_ctx.prompt_ids[0]
                if trace_ctx.tool_ids:
                    override_fields["tool_ids"] = list(trace_ctx.tool_ids)
                if trace_ctx.instruction_ids:
                    override_fields["instruction_ids"] = list(
                        trace_ctx.instruction_ids
                    )
                synth_agent = (
                    base_agent.model_copy(update=override_fields)
                    if override_fields
                    else base_agent
                )

                # Load resources the synth references so downstream
                # lookups (prompts_by_id / instructions_by_id /
                # all_tool_dicts) can resolve them, even if ws_ctx
                # didn't include them (it was scored for the test
                # orchestrator system, which probably has a different
                # tool/prompt set).
                synth_prompt_ids = (
                    [synth_agent.prompt_id] if synth_agent.prompt_id else []
                )
                synth_tool_ids = list(synth_agent.tool_ids or [])
                synth_instruction_ids = list(synth_agent.instruction_ids or [])

                async with pool.acquire() as conn:
                    extra_prompts = (
                        await get_prompts(
                            conn, synth_prompt_ids, redis, bypass_cache=True
                        )
                        if synth_prompt_ids
                        else []
                    )
                    extra_instructions = (
                        await get_instructions(
                            conn, synth_instruction_ids, redis, bypass_cache=True
                        )
                        if synth_instruction_ids
                        else []
                    )
                    extra_tools = (
                        await get_tools(
                            conn, synth_tool_ids, redis, bypass_cache=True
                        )
                        if synth_tool_ids
                        else []
                    )

                # Override the dispatch-time view: only the synth
                # agent is dispatchable, and the resource maps are
                # rebuilt from the synth's own bundle so build_agent_dispatch
                # / prompts_by_id / instructions_by_id all resolve.
                # We deliberately do NOT mutate ws_ctx (frozen) — only
                # the locals the dispatch loop reads from.
                trace_dispatch_agent = synth_agent
                agents_by_id = {synth_agent.id: synth_agent}
                config_agents = [synth_agent]
                # Replace ws_ctx slot-for-slot via local rebinds. The
                # dispatch loop reads ws_ctx.tools / .prompts /
                # .instructions later — rebind them too.
                from dataclasses import replace as _dc_replace
                ws_ctx = _dc_replace(
                    ws_ctx,
                    agents=[synth_agent],
                    tools=extra_tools,
                    prompts=extra_prompts,
                    instructions=extra_instructions,
                )
                # Existing models_by_id / providers_by_id keep working
                # since the synth's model_id is unchanged from the
                # canonical agent (already in ws_ctx.models).

    # --- Step 4: Agent groups via canonical modality-first selection ---
    #
    # Selection rules (see tool_graph.score_agents):
    #   1. Input-modality filter:  request.in ⊆ agent.input_modalities
    #   2. Output-modality filter: request.out ⊆ agent.output_modalities
    #   3. Tool filter (only when operations requested): every requested
    #      (artifact, op) must be present in agent.tool_targets
    #   4. Least-privilege rank: ascending
    #      (len(out), len(in), len(tools), str(agent_id))
    #
    # Selection vocabulary is strictly the **model** modality set
    # ``{text, audio, image, video, call}`` — derived directly from the
    # fields the request actually carries. The dispatch layer's
    # ``audio_stream`` marker (produced by ``_resolve_modality_pair`` for
    # the executor classifier) is a separate concern and never enters
    # this set.
    selection_in_mods: set[str] = set()
    if payload.audios_id or payload_params.get("audios_id"):
        # One-shot audio input (e.g. STT post-realtime turn).
        selection_in_mods.add("audio")
    if (
        payload.conversation_id
        or payload_metadata.get("conversation_id")
        or payload_params.get("conversation_id")
    ):
        # Live realtime audio. At the model level it's still ``audio``
        # input — the live-stream-vs-one-shot distinction is encoded as
        # ``audio_stream`` only on the dispatch side, for the executor.
        selection_in_mods.add("audio")
    if payload.instructions or payload.extra_messages:
        selection_in_mods.add("text")

    # Output modalities: caller-declared (no implicit defaults at the
    # selection layer for input; output keeps the API-level default of
    # ``{text, call}`` to preserve agentic-text-loop behavior when the
    # caller omits modalities — this is a request-shape default, not a
    # selection hack).
    selection_out_mods: set[str] = (
        set(payload.modalities) if payload.modalities else {"text", "call"}
    )

    tool_graph = getattr(ws_ctx, "tool_graph", None)
    available_agents = list(getattr(tool_graph, "agents", []) or [])

    agent_groups: dict[uuid.UUID, list[str]] = {}

    if trace_dispatch_agent is not None:
        # Trace replay path — bypass scoring entirely. The synth agent
        # is the only dispatch target; resource_types stay empty since
        # replay isn't materializing artifact resources, just running
        # the LLM with the historical bundle.
        agent_groups[trace_dispatch_agent.id] = []
    else:
        ranked = score_agents(
            agents=available_agents,
            request_input_modalities=selection_in_mods,
            request_output_modalities=selection_out_mods,
            artifact_type=artifact_type,
            operations=payload.operations,
        )

        logger.info(
            f"GENERATE_ATTEMPT: score_agents in={sorted(selection_in_mods)} "
            f"out={sorted(selection_out_mods)} ops={payload.operations or []} "
            f"candidates={[ (a.agent_id, sorted(a.output_modalities)) for a in ranked ]}"
        )

        if payload.operations:
            # Operations: greedy cover by best-ranked agents. Walk the
            # ranked list, pick agents that contribute uncovered
            # (artifact, op) pairs until every requested op is covered.
            # Least-privilege ranking ensures a narrower agent (e.g.
            # Attempt) is preferred over a broader one (e.g. Attempt
            # Realtime) when both cover the ops.
            requested = {(artifact_type, op) for op in payload.operations}
            uncovered = set(requested)
            for agent in ranked:
                gained = agent.tool_targets & uncovered
                if not gained:
                    continue
                agent_groups[agent.agent_id] = sorted({a for (a, _) in gained})
                uncovered -= gained
                if not uncovered:
                    break

            # Loud failure when no agent (or no combination of agents)
            # can serve the requested ops. Silent dispatches=0 leaves
            # the user staring at an empty chat with no signal — much
            # easier to diagnose seed/agent/tool wiring drift here than
            # downstream. Two distinct failure modes:
            #   - ranked is empty: no agent matched modalities + ops.
            #   - ranked non-empty but ``uncovered`` non-empty: some
            #     ops have no agent that owns the matching tool.
            if not ranked:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No {artifact_type} agent matches input "
                        f"modalities {sorted(selection_in_mods)} + "
                        f"output modalities {sorted(selection_out_mods)} "
                        f"+ ops {sorted(payload.operations)}. "
                        "Check agents seed: at least one agent for this "
                        "artifact must own the tool resources covering "
                        "every requested op."
                    ),
                )
            if uncovered:
                missing_ops = sorted({op for (_, op) in uncovered})
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No {artifact_type} agent owns tool resources "
                        f"for ops {missing_ops}. Ranked agents: "
                        f"{[a.agent_id for a in ranked]}. Either add "
                        "the missing tool to an existing agent's "
                        "``tool_ids`` or drop the op from the request."
                    ),
                )
        elif ranked:
            # No operations — pure modality conversion (STT, TTS) or a
            # tool-less variant. Pick the single best agent, empty
            # target list (executor doesn't iterate resource_types for
            # these).
            agent_groups[ranked[0].agent_id] = []

    # --- Step 5: Enrich tools ---
    config_tools = ws_ctx.tools
    all_tool_dicts = convert_tools_to_dict(config_tools) or []
    all_tool_dicts = enrich_tools_with_args(all_tool_dicts, config_tools, ws_ctx.args)
    all_tool_dicts = enrich_tools_with_args_outputs(
        all_tool_dicts, config_tools, ws_ctx.args_outputs
    )
    all_tool_dicts = enrich_tools_with_permissions(
        all_tool_dicts, config_tools, ws_ctx.permissions
    )

    prompts_by_id = {p.id: p for p in ws_ctx.prompts}
    instructions_by_id = {i.id: i for i in ws_ctx.instructions}

    tool_instructions_by_id = {i.id: i for i in ws_ctx.tool_instructions}
    all_tool_dicts = enrich_tools_with_instruction_templates(
        all_tool_dicts, config_tools, tool_instructions_by_id
    )

    # --- Step 6: Create or reuse run ---
    agent_ids_for_run = [aid for aid in agent_groups if aid]

    # ``client_run_id`` lets the FE pre-pick the run_id it expects so it
    # can subscribe to per-run events before the server creates the row.
    # Falls through to the auto-uuidv7 path when absent.
    client_run_uuid: UUID | None = None
    if payload.client_run_id:
        try:
            client_run_uuid = uuid.UUID(payload.client_run_id)
        except (ValueError, TypeError):
            client_run_uuid = None

    # The run row, the eval scaffold (setup_generation_test), and the
    # per-agent framing messages form one logical pre-execute scaffold.
    # They were previously written across three separate pool.acquire()
    # calls (S-C) — a failure mid-scaffold left a committed active run with
    # only part of its framing (and possibly a partial test). They are all
    # DB-only writes (create_run / setup_generation_test / persist_run_message
    # touch only Postgres + local redis cache + a local text-upload file — no
    # LLM/network call sits between them), so we group them into ONE
    # transaction below. The per-agent group-history reads (fetch_group_history)
    # are pulled OUT of that transaction into a separate pass so the write txn
    # stays tight and never spans an unrelated read.
    #
    # When the caller supplies its own run_id (grading-pipeline reuse), the
    # run already exists, so create_run is skipped — but the eval scaffold +
    # messages still commit atomically relative to each other.
    reuse_run_id: UUID | None = None
    if payload.run_id:
        reuse_run_id = (
            uuid.UUID(payload.run_id)
            if isinstance(payload.run_id, str)
            else payload.run_id
        )

    # --- Step 7: Setup generation test ---
    test_id: UUID | None = None
    eval_setup = None  # type: EvalSetup | None

    agents_with_rubrics = [
        AgentTestConfig(
            agent_id=a.id,
            rubric_id=a.rubric_id,
            department_ids=a.department_ids or None,
            prompt_ids=[a.prompt_id] if getattr(a, "prompt_id", None) else None,
            instruction_ids=a.instruction_ids or None,
            tool_ids=a.tool_ids or None,
        )
        for a in config_agents
        if getattr(a, "rubric_id", None)
    ]

    generation_invocation_map: dict[uuid.UUID, uuid.UUID] | None = None
    rubric_by_agent: dict[uuid.UUID, uuid.UUID] = {
        a.id: a.rubric_id for a in config_agents if getattr(a, "rubric_id", None)
    }

    # --- Step 8: Build dispatches (sync, no DB) ---
    # Pass 1: build every agent's dispatch synchronously (build_agent_dispatch
    # is pure CPU — no await). We collect the per-agent locals the message
    # persist + the later history-threading pass need, WITHOUT touching the DB
    # yet, so the scaffold write below can be a single tight transaction.
    dispatches: list[AgentDispatch] = []
    built_dispatches: list[tuple[uuid.UUID, Any, Any, dict[str, Any], Any]] = []

    for agent_group_id, agent_resource_types in agent_groups.items():
        agent_resource = agents_by_id.get(agent_group_id) or config_agents[0]

        llm_config = resolve_agent_config(agent_resource, models_by_id, providers_by_id)
        if not llm_config:
            continue

        # Resolve prompt + instructions for this agent
        pid = getattr(agent_resource, "prompt_id", None)
        prompt_obj = prompts_by_id.get(pid) if pid else None
        system_prompt = (
            (getattr(prompt_obj, "system_prompt", "") or "") if prompt_obj else ""
        )

        iids = getattr(agent_resource, "instruction_ids", None) or []
        dev_templates = [
            instructions_by_id[iid].template
            for iid in iids
            if iid in instructions_by_id and instructions_by_id[iid].template
        ]

        # Per-dispatch metadata is passthrough — eval scaffolding rides
        # on ``PrepareGenerationResult.eval_setup`` as a first-class
        # field, not stuffed into a dict bucket. Keep this assignment
        # so any caller-supplied metadata still flows.
        enriched_metadata = dict(payload_metadata)

        # Build dispatch (messages + scoped tools)
        dispatch = build_agent_dispatch(
            agent_id=agent_group_id,
            agent_resource_types=agent_resource_types,
            agent=agent_resource,
            llm_config=llm_config,
            all_tool_dicts=all_tool_dicts,
            system_prompt=system_prompt,
            developer_instruction_templates=dev_templates,
            payload_metadata=enriched_metadata,
            save=None,
            operations=payload.operations,
            artifact_type=artifact_type,
            dangerous=payload.dangerous,
            group_id=str(group_id),
            params=payload_params,
        )

        built_dispatches.append(
            (agent_group_id, agent_resource_types, llm_config, enriched_metadata, dispatch)
        )

    # --- Step 9: Atomic pre-execute scaffold write (S-C) ---
    # run row + eval scaffold + ALL framing messages in ONE transaction so a
    # mid-scaffold failure leaves no partial run / eval / messages. All three
    # are DB-only (no LLM/network call between them), so a single transaction
    # is correct; the history-threading reads stay outside it (Step 10).
    if agents_with_rubrics:
        from app.infra.websocket.generation_types import EvalSetup, InvocationSlot

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            if reuse_run_id is not None:
                run_id = reuse_run_id
            else:
                run = await create_run(
                    conn, redis,
                    group_id=group_id,
                    session_id=session_id,
                    agent_ids=agent_ids_for_run,
                    soft=soft,
                    id=client_run_uuid,
                )
                run_id = run.id

            if agents_with_rubrics:
                gen_test = await setup_generation_test(
                    conn,
                    agents=agents_with_rubrics,
                    run_id=run_id,
                    profile_id=profiles_id,
                )
                generation_invocation_map = gen_test.invocations
                test_id = gen_test.test_id

                # Build the run-level eval scaffold once. Rides on the
                # ArtifactGenerateResponse so audit's ``**output`` spread
                # carries it onto ``<artifact>.generate.completed`` — no
                # emit-time lookup, no metadata digging on the FE.
                eval_setup = EvalSetup(
                    test_id=gen_test.test_id,
                    invocations=[
                        InvocationSlot(
                            invocation_id=inv_id,
                            agent_id=agent_id,
                            rubric_id=rubric_by_agent.get(agent_id),
                        )
                        for agent_id, inv_id in gen_test.invocations.items()
                    ],
                )

            # Persist every agent's framing messages to the run, same conn/txn.
            for _agid, _art, _llm, _meta, dispatch in built_dispatches:
                for msg in dispatch.messages:
                    if msg.persist:
                        await persist_run_message(
                            conn,
                            redis,
                            run_id=run_id,
                            session_id=session_id,
                            role=msg.role,
                            content=msg.raw_text,
                        )

                # Instructions — role is "user" for FE-direct flows (a human
                # typed something) and "assistant" for tool-driven flows
                # (the parent LLM crafted these as a tool argument, e.g.
                # ``Scenario_Generate(instructions=["…"])``). Caller decides
                # via ``payload.instructions_role`` (default "user"); the
                # INFRA_OPS tool dispatcher overrides to "assistant".
                if payload.instructions:
                    for instruction in payload.instructions:
                        await persist_run_message(
                            conn,
                            redis,
                            run_id=run_id,
                            session_id=session_id,
                            role=payload.instructions_role,
                            content=instruction,
                        )

    # --- Step 10: Thread history + assemble dispatches (reads, no write txn) ---
    for agent_group_id, agent_resource_types, llm_config, enriched_metadata, dispatch in built_dispatches:

        # Resolve this agent's full input-modality set from the tool
        # graph so chat-history rendering can decide between OpenAI
        # tool_calls format (when "call" ∈ input_modalities) and the
        # plain-text fallback. Falls back to {"text"} if the agent
        # somehow isn't in the graph (defensive — shouldn't happen).
        _agent_in_mods: set[str] = {"text"}
        if tool_graph is not None:
            for _ag in getattr(tool_graph, "agents", []) or []:
                if getattr(_ag, "id", None) == agent_group_id:
                    _agent_in_mods = set(_ag.input_modalities or {"text"})
                    break

        # Modality-filter the group's prior messages and splice in
        # between the system+developer framing and the current user
        # instruction. Each dispatch sees its own version because
        # different agents in a multi-agent run can have different
        # input modalities. See render_history.py for the role × call
        # support truth table.
        from app.infra.generation.chat_history import fetch_group_history
        from app.infra.generation.render_history import (
            render_history_for_dispatch,
        )

        rendered_history: list[dict[str, Any]] = []
        if group_id is not None and tool_graph is not None:
            try:
                _raw_history = await fetch_group_history(
                    pool,
                    group_id=group_id,
                    exclude_run_id=run_id,
                    agent_id=agent_group_id,
                )
                rendered_history = render_history_for_dispatch(
                    _raw_history,
                    input_modalities=_agent_in_mods,
                    scoped_tools=dispatch.scoped_tools,
                )
                # Mark history items so each artifact's per-generate
                # emit loop skips them. ``dispatch.messages`` carries
                # both new framing (system + developer + current user
                # instruction) AND threaded history; only the former
                # should fire as ``{artifact}.generate.text.complete``
                # live events. The frontend already shows historicals
                # via the group_get path — re-emitting them as live
                # events produces duplicate bubbles.
                for _h in rendered_history:
                    _h["_emit"] = False
            except Exception as e:
                # History threading is enhancement, not required —
                # never fail a generation because we couldn't load it.
                logger.warning(
                    "fetch/render group history failed for group %s "
                    "(non-fatal): %r",
                    group_id, e,
                )

        # Collect all messages for LLM
        all_messages = list(dispatch.messages_for_llm)
        if rendered_history:
            all_messages.extend(rendered_history)
        if payload.extra_messages:
            for em in payload.extra_messages:
                all_messages.append(em)
        if payload.instructions:
            # Role mirrors the persistence path above (~line 685): "user"
            # for FE-direct flows, "assistant" for tool-driven flows. The
            # live ``text.complete`` emit reads this list, so a hardcoded
            # "user" here would render the assistant-crafted instructions
            # as a user bubble even though the persisted row has
            # role=assistant.
            for instruction in payload.instructions:
                all_messages.append(
                    {"role": payload.instructions_role, "content": instruction}
                )

        _params = payload_params or {}
        _meta = enriched_metadata or {}
        dispatch_chat_id = (
            _meta.get("chat_id") or _params.get("chat_id")
        )
        dispatch_conversation_id = (
            payload.conversation_id
            or _meta.get("conversation_id")
            or _params.get("conversation_id")
        )
        dispatch_audios_id = payload.audios_id or _params.get("audios_id")
        input_mods, output_mods = _resolve_modality_pair(
            modalities=payload.modalities,
            audios_id=dispatch_audios_id,
            conversation_id=dispatch_conversation_id,
        )

        dispatches.append(AgentDispatch(
            agent_id=agent_group_id,
            messages=all_messages,
            tools=dispatch.scoped_tools,
            llm_config={
                "model": llm_config.model,
                "api_key": llm_config.api_key,
                "base_url": llm_config.base_url,
                "temperature": llm_config.temperature,
                "reasoning": llm_config.reasoning,
                "provider": llm_config.provider,
                "voice": llm_config.voice,
                "quality": llm_config.quality,
                "length_seconds": None,
                "tool_choice": "required",
            },
            resource_types=agent_resource_types,
            metadata=enriched_metadata or None,
            developer_instruction_templates=dispatch.developer_instruction_templates,
            input_modalities=input_mods,
            output_modalities=output_mods,
            chat_id=str(dispatch_chat_id) if dispatch_chat_id else None,
            conversation_id=str(dispatch_conversation_id) if dispatch_conversation_id else None,
            audios_id=str(dispatch_audios_id) if dispatch_audios_id else None,
        ))

    return PrepareGenerationResult(
        run_id=run_id,
        group_id=group_id,
        session_id=session_id,
        profile_id=profile_id,
        profiles_id=profiles_id,
        artifact_type=artifact_type,
        dispatches=dispatches,
        test_id=test_id,
        resource_types=resource_types,
        eval=eval_run,
        eval_setup=eval_setup,
        # Forward caller-supplied label + derive description from the
        # instructions when none was provided. Media dispatches consume
        # both to stamp the produced ``{m}s_resource`` row with
        # human-readable values.
        title=payload.title,
        description=(
            "\n\n".join(payload.instructions)
            if payload.instructions
            else None
        ),
    )
