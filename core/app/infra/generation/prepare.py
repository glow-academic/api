"""Generation prepare — deterministic infra function.

Extracts the proven prepare logic from generate_prepare_impl into a
callable function. Uses the exact same helper functions — no new logic.

Creates all DB state needed for execution:
  1. resolve_websocket_context → agents, tools, prompts, models
  2. Enrich tools (args, args_outputs, permissions, instruction templates)
  3. Build agent groups from scores
  4. create_run (active=not soft, linked to agents)
  5. persist_run_message — system, developer, user messages
  6. setup_generation_test — test + invocations if rubrics
  7. init_run_trackers — Redis progress tracking
  8. Returns PrepareGenerationResult with agent dispatches
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import asyncpg

from app.infra.generation import convert_tools_to_dict
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.types import ArtifactRequest
from app.infra.websocket.generation_types import GeneratePayload
from app.infra.websocket.init_run_trackers import init_run_trackers
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.run_tracker import WorkUnit
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
    """Resolve (input_modalities, output_modalities) for a dispatch.

    Inputs are inferred from the request payload:
      - conversation_id present → live streaming audio input
      - audios_id present → one-shot audio input (STT)
      - otherwise → text input

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


def _build_work_units(
    agent_groups: dict[uuid.UUID, list[str]],
    createable_resources: set[str] | list[str],
) -> list[WorkUnit]:
    """Build run-tracker work units from grouped agent resource assignments."""
    createable = set(createable_resources)
    return [
        WorkUnit(
            agent_id=str(aid),
            target_type="resource" if rt in createable else "entry",
            target_name=rt,
        )
        for aid, rts in agent_groups.items()
        for rt in rts
    ]


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

    Uses the same proven pipeline functions as generate_prepare_impl.
    Returns PrepareGenerationResult with all dispatches ready for execution.

    When soft=True, run is created with active=false — everything is set up
    but nothing executes until accepted.
    """
    from app.infra.websocket.prepare_pipeline import (
        build_agent_dispatch,
        build_agent_groups_from_scores,
        compute_createable_resources,
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

    # --- Step 4: Agent groups from scores ---
    if payload.operations:
        dispatch_types = [artifact_type]
    else:
        dispatch_types = resource_types

    agent_groups = build_agent_groups_from_scores(
        resource_types=dispatch_types,
        scores=ws_ctx.scores,
        operations=payload.operations,
        artifact_type=artifact_type,
        tool_graph=getattr(ws_ctx, "tool_graph", None),
        modalities=payload.modalities,
    )

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
    createable_resources = compute_createable_resources(config_tools)

    prompts_by_id = {p.id: p for p in ws_ctx.prompts}
    instructions_by_id = {i.id: i for i in ws_ctx.instructions}

    tool_instructions_by_id = {i.id: i for i in ws_ctx.tool_instructions}
    all_tool_dicts = enrich_tools_with_instruction_templates(
        all_tool_dicts, config_tools, tool_instructions_by_id
    )

    # --- Step 6: Create or reuse run ---
    agent_ids_for_run = [aid for aid in agent_groups if aid]

    if payload.run_id:
        # Reuse existing run (e.g., grading pipeline passes its own run_id)
        run_id = uuid.UUID(payload.run_id) if isinstance(payload.run_id, str) else payload.run_id
    else:
        async with pool.acquire() as conn:
            run = await create_run(
                conn,
                group_id=group_id,
                session_id=session_id,
                agent_ids=agent_ids_for_run,
                soft=soft,
            )
        run_id = run.id

    # --- Step 7: Init trackers ---
    units = _build_work_units(agent_groups, createable_resources)
    await init_run_trackers(
        redis,
        run_id=str(run_id),
        num_agents=len(agent_groups),
        num_resources=len(resource_types),
        units=units,
    )

    # --- Step 8: Setup generation test ---
    test_id: UUID | None = None

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

    generation_test_id: str | None = None
    generation_invocation_map: dict[uuid.UUID, uuid.UUID] | None = None

    if agents_with_rubrics:
        async with pool.acquire() as conn:
            gen_test = await setup_generation_test(
                conn,
                agents=agents_with_rubrics,
                run_id=run_id,
                profile_id=profiles_id,
            )
        generation_test_id = str(gen_test.test_id)
        generation_invocation_map = gen_test.invocations
        test_id = gen_test.test_id

    # --- Step 9: Build dispatches + persist messages ---
    dispatches: list[AgentDispatch] = []

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

        # Enrich metadata with test + resolution config
        enriched_metadata = dict(payload_metadata)
        if generation_test_id:
            enriched_metadata["generation_test_id"] = generation_test_id
            if generation_invocation_map and agent_group_id in generation_invocation_map:
                enriched_metadata["test_invocation_id"] = str(
                    generation_invocation_map[agent_group_id]
                )
        if ws_ctx.resolution_strategy:
            enriched_metadata["resolution_strategy"] = ws_ctx.resolution_strategy
        if ws_ctx.resolution_threshold is not None:
            enriched_metadata["resolution_threshold"] = ws_ctx.resolution_threshold

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

        # Persist messages to the run
        async with pool.acquire() as conn:
            for msg in dispatch.messages:
                if msg.persist:
                    await persist_run_message(
                        conn,
                        run_id=run_id,
                        session_id=session_id,
                        role=msg.role,
                        content=msg.raw_text,
                    )

            # User instructions
            if payload.instructions:
                for instruction in payload.instructions:
                    await persist_run_message(
                        conn,
                        run_id=run_id,
                        session_id=session_id,
                        role="user",
                        content=instruction,
                    )

        # Collect all messages for LLM
        all_messages = list(dispatch.messages_for_llm)
        if payload.extra_messages:
            for em in payload.extra_messages:
                all_messages.append(em)
        if payload.instructions:
            for instruction in payload.instructions:
                all_messages.append({"role": "user", "content": instruction})

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
    )
