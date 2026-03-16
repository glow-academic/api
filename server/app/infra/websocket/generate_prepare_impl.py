"""Generation preparation — pure business logic with emit: EmitFn.

Resolves context, creates run, builds agent dispatches, persists messages,
and emits generate_artifact events.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from app.infra.generation import convert_tools_to_dict
from app.infra.generation.media_context import wrap_media_entries
from app.infra.types import ArtifactRequest
from app.infra.websocket.generation_types import (
    GenerateArtifactPayload,
    GenerateErrorApiRequest,
    GeneratePayload,
    GenerationStartedData,
)
from app.infra.websocket.init_run_trackers import init_run_trackers
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.run_tracker import WorkUnit
from app.infra.websocket.setup_generation_test import (
    AgentTestConfig,
    setup_generation_test,
)
from app.infra.websocket.socket_event import EmitFn, SocketEvent, internal_event
from app.infra.websocket_context import resolve_websocket_context
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ResolveWebsocketContextFn = Callable[..., Awaitable[Any]]
FetchEntryTypesFn = Callable[[list[Any], Any], Awaitable[dict[str, dict[str, Any]]]]
BuildAgentGroupsFromScoresFn = Callable[..., dict[uuid.UUID, list[str]]]
BuildJinjaFromWsCtxFn = Callable[..., dict[str, Any]]
ResolveAgentConfigFn = Callable[..., Any]
BuildAgentDispatchFn = Callable[..., Any]
CreateRunFn = Callable[..., Awaitable[Any]]
InitRunTrackersFn = Callable[..., Awaitable[None]]
PersistRunMessageFn = Callable[..., Awaitable[None]]
SetupGenerationTestFn = Callable[..., Awaitable[Any]]
ValidatePayloadFn = Callable[..., str | None]


def resolve_primary_artifact_type(data: dict[str, Any]) -> str:
    """Resolve the primary artifact type name from raw request data."""
    artifact_types_raw = data.get("artifact_types") or []
    if artifact_types_raw and isinstance(artifact_types_raw[0], dict):
        return artifact_types_raw[0].get("name", "unknown")
    return "unknown"


def parse_generation_identity(
    data: dict[str, Any],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Parse the required UUID identity fields for generation preparation."""
    return (
        uuid.UUID(data["profile_id"]),
        uuid.UUID(data["profiles_id"]),
        uuid.UUID(data["session_id"]),
        uuid.UUID(data["group_id"]),
    )


def build_generation_work_units(
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


def enrich_generation_metadata(
    payload_metadata: dict[str, Any],
    *,
    generation_test_id: str | None,
    generation_invocation_map: dict[uuid.UUID, uuid.UUID] | None,
    agent_group_id: uuid.UUID,
) -> dict[str, Any]:
    """Add generation-test metadata for one agent dispatch when available."""
    enriched_metadata = dict(payload_metadata)
    if generation_test_id:
        enriched_metadata["generation_test_id"] = generation_test_id
        if generation_invocation_map and agent_group_id in generation_invocation_map:
            enriched_metadata["test_invocation_id"] = str(
                generation_invocation_map[agent_group_id]
            )
    return enriched_metadata


def build_generation_started_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    resource_types: list[str],
) -> dict[str, Any]:
    """Build the generation_started internal payload."""
    return GenerationStartedData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        resource_types=resource_types,
    ).model_dump(mode="json")


def build_generate_artifact_payload(
    *,
    sid: str,
    artifact_type: str,
    agent_resource_types: list[str],
    run_id: str,
    group_id: str,
    modality: str,
    all_messages: list[dict[str, Any]],
    llm_config: Any,
    scoped_tools: list[dict[str, Any]],
    metadata: dict[str, Any] | None,
    profile_id: str,
    profiles_id: str,
    session_id: str,
    artifact_id: uuid.UUID | None,
    draft_id: uuid.UUID | None,
    developer_instruction_templates: list[str] | None,
    agent_id: uuid.UUID,
) -> dict[str, Any]:
    """Build the generate_artifact internal payload for one agent dispatch."""
    return GenerateArtifactPayload(
        sid=sid,
        artifact_type=artifact_type,
        resource_type=agent_resource_types[0]
        if agent_resource_types
        else artifact_type,
        run_id=run_id,
        group_id=group_id,
        modality=modality,
        message_id=None,
        messages=all_messages,
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
        tools=scoped_tools,
        metadata=metadata or None,
        profile_id=profile_id,
        profiles_id=profiles_id,
        session_id=session_id,
        artifact_id=str(artifact_id) if artifact_id else None,
        draft_id=str(draft_id) if draft_id else None,
        developer_instruction_templates=developer_instruction_templates,
        agent_id=str(agent_id),
    ).model_dump(mode="json")


async def generate_prepare_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    conn: asyncpg.Connection,
    redis: Any,
    artifact_config: Any,
    validate_payload_fn: ValidatePayloadFn | None = None,
    resolve_websocket_context_fn: ResolveWebsocketContextFn | None = None,
    fetch_entry_types_fn: FetchEntryTypesFn | None = None,
    build_agent_groups_from_scores_fn: BuildAgentGroupsFromScoresFn | None = None,
    build_jinja_from_ws_ctx_fn: BuildJinjaFromWsCtxFn | None = None,
    resolve_agent_config_fn: ResolveAgentConfigFn | None = None,
    build_agent_dispatch_fn: BuildAgentDispatchFn | None = None,
    create_run_fn: CreateRunFn | None = None,
    init_run_trackers_fn: InitRunTrackersFn | None = None,
    persist_run_message_fn: PersistRunMessageFn | None = None,
    setup_generation_test_fn: SetupGenerationTestFn | None = None,
) -> None:
    """Handle generate_prepare — orchestrate context resolution and dispatch.

    Expects session_id, profile_id, group_id already in data
    (resolved by client handler, propagated through internal/generate).

    Args:
        artifact_config: ArtifactGenerateConfig from the registry for this artifact_type.
    """
    sid = data.get("sid", "")

    artifact_type = resolve_primary_artifact_type(data)

    # Identity context
    profile_id_str = data.get("profile_id")
    profiles_id_str = data.get("profiles_id")
    session_id_str = data.get("session_id")
    group_id_str = data.get("group_id")

    if not profile_id_str:
        await _emit_error(
            emit,
            sid,
            "Profile not found. Please reconnect." if sid else "Profile not found.",
            artifact_type,
        )
        return

    if not profiles_id_str:
        await _emit_error(
            emit,
            sid,
            "Profiles resource not found. Please reconnect."
            if sid
            else "Profiles resource not found.",
            artifact_type,
        )
        return

    if not session_id_str:
        await _emit_error(
            emit,
            sid,
            "Session not found. Please reconnect." if sid else "Session not found.",
            artifact_type,
        )
        return

    if not group_id_str:
        await _emit_error(emit, sid, "group_id is required.", artifact_type)
        return

    try:
        profile_id, profiles_id, session_id, group_id = parse_generation_identity(
            {
                "profile_id": profile_id_str,
                "profiles_id": profiles_id_str,
                "session_id": session_id_str,
                "group_id": group_id_str,
            }
        )
        payload = GeneratePayload(**data)
    except Exception as e:
        await _emit_error(emit, sid, f"Invalid request: {str(e)}", artifact_type)
        return

    if not artifact_config:
        await _emit_error(
            emit, sid, f"Unknown artifact_type: {artifact_type}", artifact_type
        )
        return

    try:
        from app.infra.websocket.prepare_pipeline import (
            build_agent_dispatch,
            build_agent_groups_from_scores,
            build_jinja_from_ws_ctx,
            compute_all_artifact_types,
            compute_createable_resources,
            enrich_tools_with_args,
            enrich_tools_with_args_outputs,
            resolve_agent_config,
            validate_payload,
        )
        from app.tools.entries.runs.create import create_run

        validate_payload_fn = validate_payload_fn or validate_payload
        resolve_websocket_context_fn = (
            resolve_websocket_context_fn or resolve_websocket_context
        )
        fetch_entry_types_fn = fetch_entry_types_fn or _fetch_entry_types
        build_agent_groups_from_scores_fn = (
            build_agent_groups_from_scores_fn or build_agent_groups_from_scores
        )
        build_jinja_from_ws_ctx_fn = (
            build_jinja_from_ws_ctx_fn or build_jinja_from_ws_ctx
        )
        resolve_agent_config_fn = resolve_agent_config_fn or resolve_agent_config
        build_agent_dispatch_fn = build_agent_dispatch_fn or build_agent_dispatch
        create_run_fn = create_run_fn or create_run
        init_run_trackers_fn = init_run_trackers_fn or init_run_trackers
        persist_run_message_fn = persist_run_message_fn or persist_run_message
        setup_generation_test_fn = setup_generation_test_fn or setup_generation_test

        # --- Step 1: Validate (pure) ---
        resource_types = [rt.name for rt in payload.resource_types if rt]
        error = validate_payload_fn(
            resource_types_raw=resource_types,
            artifact_type=artifact_type,
            valid_resource_types=artifact_config.valid_resource_types,
            entry_types=artifact_config.entry_types,
            requires_draft=artifact_config.requires_draft,
            draft_id=payload.draft_id,
        )
        if error:
            await _emit_error(emit, sid, error, artifact_type)
            return

        # --- Step 2: Resolve artifact_id ---
        artifact_id = payload.artifact_id
        payload_metadata = payload.metadata or {}
        if (
            artifact_type == "profile"
            and not artifact_id
            and payload_metadata.get("staff_id")
        ):
            artifact_id = uuid.UUID(payload_metadata["staff_id"])

        # --- Steps 3–7: Resolve context ---
        bypass_cache = True

        ws_ctx = await resolve_websocket_context_fn(
            pool,
            redis,
            profile_id=profile_id,
            requests=[
                ArtifactRequest(
                    artifact_type=artifact_type,
                    artifact_id=artifact_id,
                    group_id=group_id,
                    draft_id=payload.draft_id,
                )
            ],
            bypass_cache=bypass_cache,
        )

        if ws_ctx is None:
            await _emit_error(emit, sid, "Failed to resolve context.", artifact_type)
            return

        if not ws_ctx.agents:
            await _emit_error(
                emit, sid, "No system/agent configuration found.", artifact_type
            )
            return

        # Lookups from ws_ctx
        agents_by_id = {a.id: a for a in ws_ctx.agents}
        models_by_id = {m.id: m for m in ws_ctx.models}
        providers_by_id = {p.id: p for p in ws_ctx.providers}
        config_agents = ws_ctx.agents

        # Agent groups from tool scores
        agent_groups = build_agent_groups_from_scores_fn(
            resource_types=resource_types,
            scores=ws_ctx.scores,
        )

        # Jinja context
        entry_results: dict[str, dict[str, Any]] | None = None
        if payload.entry_types:
            entry_results = await fetch_entry_types_fn(payload.entry_types, conn)

        jinja_context_base = build_jinja_from_ws_ctx_fn(ws_ctx, entry_results)
        wrap_media_entries(jinja_context_base)

        # Tools
        config_tools = ws_ctx.tools
        all_tool_dicts = convert_tools_to_dict(config_tools) or []
        all_tool_dicts = enrich_tools_with_args(
            all_tool_dicts, config_tools, ws_ctx.args
        )
        all_tool_dicts = enrich_tools_with_args_outputs(
            all_tool_dicts, config_tools, ws_ctx.args_outputs
        )
        createable_resources = compute_createable_resources(config_tools)
        all_artifact_types = compute_all_artifact_types(all_tool_dicts)

        # Prompts/instructions
        prompts_by_id = {p.id: p for p in ws_ctx.prompts}
        instructions_by_id = {i.id: i for i in ws_ctx.instructions}

        # --- Step 8: Create run ---
        agent_ids_for_run = [aid for aid in agent_groups if aid]
        run = await create_run_fn(
            conn,
            group_id=group_id,
            session_id=session_id,
            profiles_id=profiles_id,
            agent_ids=agent_ids_for_run,
        )
        run_id = run.id

        # --- Step 9: Init trackers ---
        units = build_generation_work_units(agent_groups, createable_resources)
        await init_run_trackers_fn(
            redis,
            run_id=str(run_id),
            num_agents=len(agent_groups),
            num_resources=len(resource_types),
            units=units,
        )

        # --- Step 9b: Setup generation test ---
        generation_test_id: str | None = None
        generation_invocation_map: dict[uuid.UUID, uuid.UUID] | None = None

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

        if agents_with_rubrics:
            gen_test = await setup_generation_test_fn(
                conn,
                agents=agents_with_rubrics,
                run_id=run_id,
                profile_id=profile_id,
            )
            generation_test_id = str(gen_test.test_id)
            generation_invocation_map = gen_test.invocations

        # --- Step 10: Build dispatches + persist messages ---
        events: list[SocketEvent] = []

        events.append(
            internal_event(
                "generation_started",
                build_generation_started_payload(
                    sid=sid,
                    artifact_type=artifact_type,
                    group_id=group_id_str,
                    run_id=str(run_id),
                    resource_types=resource_types,
                ),
            )
        )

        for agent_group_id, agent_resource_types in agent_groups.items():
            agent_resource = agents_by_id.get(agent_group_id) or config_agents[0]

            llm_config = resolve_agent_config_fn(
                agent_resource, models_by_id, providers_by_id
            )
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

            # Inject generation test metadata
            enriched_metadata = enrich_generation_metadata(
                payload_metadata,
                generation_test_id=generation_test_id,
                generation_invocation_map=generation_invocation_map,
                agent_group_id=agent_group_id,
            )

            dispatch = build_agent_dispatch_fn(
                agent_id=agent_group_id,
                agent_resource_types=agent_resource_types,
                agent=agent_resource,
                llm_config=llm_config,
                jinja_context_base=jinja_context_base,
                createable_resources=createable_resources,
                all_tool_dicts=all_tool_dicts,
                all_artifact_types=all_artifact_types,
                system_prompt=system_prompt,
                developer_instruction_templates=dev_templates,
                payload_metadata=enriched_metadata,
                save=None,
            )

            # Persist messages
            for msg in dispatch.messages:
                if msg.persist:
                    await persist_run_message_fn(
                        conn,
                        run_id=run_id,
                        session_id=session_id,
                        role=msg.role,
                        content=msg.raw_text,
                    )

            # Extra messages (not persisted — pre-existing chat history)
            all_messages = list(dispatch.messages_for_llm)
            if payload.extra_messages:
                for em in payload.extra_messages:
                    all_messages.append(em)

            # User instructions (persisted)
            if payload.user_instructions:
                for instruction in payload.user_instructions:
                    all_messages.append({"role": "user", "content": instruction})
                    await persist_run_message_fn(
                        conn,
                        run_id=run_id,
                        session_id=session_id,
                        role="user",
                        content=instruction,
                    )

            # Build dispatch event
            events.append(
                internal_event(
                    "generate_artifact",
                    build_generate_artifact_payload(
                        sid=sid,
                        artifact_type=artifact_type,
                        agent_resource_types=agent_resource_types,
                        run_id=str(run_id),
                        group_id=group_id_str,
                        modality=payload.modality,
                        all_messages=all_messages,
                        llm_config=llm_config,
                        scoped_tools=dispatch.scoped_tools,
                        metadata=dispatch.metadata,
                        profile_id=profile_id_str,
                        profiles_id=profiles_id_str,
                        session_id=session_id_str,
                        artifact_id=artifact_id,
                        draft_id=payload.draft_id,
                        developer_instruction_templates=dispatch.developer_instruction_templates,
                        agent_id=agent_group_id,
                    ),
                )
            )

        # --- Step 11: Flush all events ---
        await emit(events)

    except Exception as e:
        logger.exception(f"Failed to generate {artifact_type} resources: {str(e)}")
        await _emit_error(
            emit,
            sid,
            f"Failed to generate {artifact_type} resources: {str(e)}",
            artifact_type,
        )


async def _emit_error(
    emit: EmitFn,
    sid: str,
    message: str,
    artifact_type: str,
    *,
    group_id: str | None = None,
) -> None:
    await emit(
        [
            internal_event(
                "generate_call_error",
                GenerateErrorApiRequest(
                    sid=sid,
                    error_message=message,
                    artifact_type=artifact_type,
                    group_id=group_id,
                    resource_type=artifact_type,
                ).model_dump(),
            )
        ]
    )


async def _fetch_entry_types(
    entry_types: list[Any],
    conn: Any,
) -> dict[str, dict[str, Any]]:
    """Fetch data for each entry_type item. Returns {name: {operation: data}}."""
    from app.registry.operations import ENTRY_OPS, resolve_callable

    results: dict[str, dict[str, Any]] = {}
    for item in entry_types:
        if item.operation != "get":
            continue
        fn = resolve_callable(item.name, item.operation, ENTRY_OPS)
        if fn is None:
            continue
        try:
            result = await fn(conn)
            if hasattr(result, "model_dump"):
                results.setdefault(item.name, {})[item.operation] = result.model_dump(
                    mode="json"
                )
            elif isinstance(result, list):
                results.setdefault(item.name, {})[item.operation] = [
                    r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                    for r in result
                ]
            else:
                results.setdefault(item.name, {})[item.operation] = result
        except Exception as e:
            logger.warning(
                f"Failed to fetch entry_type '{item.name}.{item.operation}': {e}"
            )
    return results
