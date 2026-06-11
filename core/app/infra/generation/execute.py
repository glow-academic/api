"""Generation execute — deterministic infra function.

Runs the agentic LLM loop for text + tool call modality.

Events emitted are artifact-scoped:
  {artifact_type}.generate.progress — text/tool streaming
  Tool calls go through execute_infra_operation → audit path
  emits {artifact}.{operation}.completed naturally.

No generic events (generate_text_progress, generate_call_complete, etc.).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from app.infra.artifacts import (
    convert_tools_to_openai_format,
    convert_tools_to_responses_format,
    format_messages_for_litellm,
    stream_litellm_events,
)
from app.infra.artifacts.convert_tools_to_openai_format import sanitize_tool_name
from app.infra.generation.audio import execute_audio_dispatch
from app.infra.generation.dispatch import resolve_executor
from app.infra.generation.emit import emit_modality_event
from app.infra.generation.media import execute_media_dispatch
from app.infra.generation.stt import execute_stt_dispatch
from app.infra.generation.tts import execute_tts_dispatch
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import get_internal_sio
from app.infra.tools.execute_infra_operation import (
    InfraContext,
    execute_infra_operation,
)
from app.infra.tools.resolve_tool_spec import resolve_tool_spec
from app.infra.websocket.generation_types import GenerateErrorApiRequest, ProducedMedia
from app.infra.websocket.is_run_cancelled import is_run_cancelled
from app.infra.websocket.set_active_run import set_active_run
from app.infra.websocket.socket_event import internal_event, make_emit
from app.infra.websocket.tool_call_utils import (
    build_tool_output_schemas,
    parse_partial_json,
    resolve_output_fields,
)
from app.utils.auth.decrypt_api_key import decrypt_api_key
from app.utils.logging.db_logger import get_logger

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

logger = get_logger(__name__)

# Cancellation message — kept identical across every Stop raise site so the
# runner's ``.generate.failed`` emit and existing ``match="stopped by user"``
# expectations stay stable. Raised as its own ``RuntimeError`` subclass (G3)
# so the dispatch wrapper can tell a user-Stop apart from a real error and
# persist the token/cost already consumed by the iterations that DID complete
# before the Stop landed, instead of dropping that billing on the floor.
_CANCEL_MESSAGE = "Generation stopped by user (/attempt/stop)"


class _GenerationCancelled(RuntimeError):
    """Raised when the cooperative ``cancel_run:{run_id}`` marker is observed.

    A ``RuntimeError`` subclass so it propagates through ``runner._run`` exactly
    like the old bare ``RuntimeError`` (same ``.generate.failed`` terminal),
    while letting ``_execute_agent_dispatch`` flush partial usage on the way out.
    """


# ---------------------------------------------------------------------------
# Tool → (artifact, operation) route resolution
# ---------------------------------------------------------------------------


def _resolve_tool_route(
    tool_def: dict[str, Any] | None,
) -> tuple[str, str] | None:
    """Return the single (artifact, operation) pair this tool resolves to.

    Per-operation progress events are only meaningful when the tool maps
    to a single operation. Multi-op tools route dynamically at exec time
    and can't pre-commit a progress channel — return None.
    """
    if not tool_def:
        return None
    perms = tool_def.get("_permissions") or []
    pairs = {
        (p.get("artifact"), p.get("operation"))
        for p in perms
        if isinstance(p, dict) and p.get("artifact") and p.get("operation")
    }
    if len(pairs) == 1:
        return next(iter(pairs))  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------------------
# Tool format validation (Responses API)
# ---------------------------------------------------------------------------


def _validate_responses_tools(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and convert tools to Responses API format."""
    validated_tools: list[dict[str, Any]] = []
    for tool in tools:
        tool_dict: dict[str, Any] | None = None
        if isinstance(tool, dict):
            tool_dict = cast(dict[str, Any], tool)
        elif hasattr(tool, "model_dump"):
            tool_dict = tool.model_dump()
        elif hasattr(tool, "dict"):
            tool_dict = tool.dict()
        if not tool_dict:
            continue
        if tool_dict.get("type") == "function" and "name" in tool_dict:
            tool_copy = {**tool_dict}
            if tool_copy.get("strict") and isinstance(
                tool_copy.get("parameters"), dict
            ):
                tool_copy["parameters"] = {
                    **tool_copy["parameters"],
                    "additionalProperties": False,
                }
            validated_tools.append(tool_copy)
        elif tool_dict.get("type") == "function" and "function" in tool_dict:
            func = tool_dict.get("function")
            if isinstance(func, dict) and func.get("name"):
                validated_tools.append(
                    {
                        "type": "function",
                        "name": func.get("name"),
                        "parameters": func.get("parameters", {}),
                        "description": func.get("description"),
                        "strict": func.get("strict"),
                    }
                )
    return validated_tools


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ExecuteGenerationResult:
    """Result from executing one or more agent dispatches."""

    run_id: uuid.UUID
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    assistant_output: str = ""
    reasoning_output: str = ""
    # Media artifacts produced by image/video dispatches in this run.
    # Populated by ``execute_media_dispatch`` and surfaced on
    # ``ArtifactGenerateResponse.produced_media`` so the calling LLM tool
    # can fetch by id without a separate watch round-trip.
    produced_media: list["ProducedMedia"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM API calls
# ---------------------------------------------------------------------------


async def _call_responses_api(
    *, model: str, responses_input: list, tools: list | None,
    tool_choice: str, api_key: str | None, base_url: str | None,
    temperature: float, extra_body: dict | None,
) -> Any:
    """Call litellm Responses API."""
    # The openai/ prefix tells litellm SDK to use OpenAI-compatible protocol.
    effective_model = f"openai/{model}" if base_url and "/" not in model else model

    # Register model for native streaming support — without this, litellm
    # falls back to MockResponsesAPIStreamingIterator which buffers events.
    if effective_model not in litellm.model_cost:
        litellm.model_cost[effective_model] = {
            "supports_native_streaming": True,
            "max_tokens": 128000,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
        }

    kwargs: dict[str, Any] = {
        "model": effective_model,
        "input": responses_input,
        "stream": True,
        "temperature": temperature,
        "api_key": api_key,
        "timeout": 120.0,
    }
    if tools:
        kwargs["tools"] = _validate_responses_tools(tools)
        kwargs["tool_choice"] = tool_choice
    if base_url:
        # aresponses() uses api_base, not base_url
        kwargs["api_base"] = base_url
    if extra_body:
        kwargs["extra_body"] = extra_body
    return await litellm.aresponses(**kwargs)


async def _call_chat_completions_api(
    *, model: str, messages: list, tools: list | None,
    tool_choice: str, api_key: str | None, base_url: str | None,
    temperature: float, reasoning: bool | None, extra_body: dict | None,
) -> Any:
    """Call litellm Chat Completions API."""
    # The openai/ prefix tells litellm SDK to use OpenAI-compatible protocol.
    effective_model = f"openai/{model}" if base_url and "/" not in model else model
    kwargs: dict[str, Any] = {
        "model": effective_model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        # Parity with the Responses path (_call_responses_api): cap the upstream
        # wait so a stalled DGX on the chat fallback can't tie up a worker for
        # litellm's ~600s default.
        "timeout": 120.0,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if extra_body:
        kwargs["extra_body"] = extra_body
    if reasoning:
        kwargs["reasoning_effort"] = "high"
    return await litellm.acompletion(**kwargs)


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------


from app.infra.server_timing import timed


async def execute_generation(
    pool: Any,
    redis: Any,
    *,
    prepared: PrepareGenerationResult,
    sid: str,
    tool_soft: bool = True,
    max_iterations: int = 15,
) -> ExecuteGenerationResult:
    """Execute the agentic LLM loop for all dispatches in the prepared result.

    For each agent dispatch:
      1. Format messages + tools for litellm
      2. Run agentic loop (stream tokens, handle tool calls)
      3. Tool calls → execute_infra_operation (audit emits artifact events)
      4. Emit artifact-scoped progress events

    Returns ExecuteGenerationResult with token usage and tool results.
    """
    internal_sio = get_internal_sio()
    emit = make_emit()
    run_id = prepared.run_id

    # Flip the eval contextvar for this task + its descendants. Every
    # ``create_soft_call`` invocation downstream (300+ callsites across
    # the impl tree) will tag its ledger row ``eval=true`` automatically
    # via the contextvar default. ``asyncio.gather`` / ``create_task``
    # inherit contextvars per PEP 567, so parallel agent fan-out picks
    # this up without per-task plumbing.
    if prepared.eval:
        from app.infra.events.eval_context import set_eval_mode
        set_eval_mode(True)

    total_result = ExecuteGenerationResult(run_id=run_id)

    async def _run_one(dispatch: AgentDispatch) -> ExecuteGenerationResult | None:
        executor = resolve_executor(
            dispatch.input_modalities, dispatch.output_modalities,
        )
        logger.info(
            f"DISPATCH executor={executor} in={sorted(dispatch.input_modalities)} "
            f"out={sorted(dispatch.output_modalities)}"
        )

        if executor == "realtime":
            await execute_audio_dispatch(
                dispatch=dispatch, prepared=prepared, sid=sid, emit=emit,
            )
            return None
        if executor == "tts":
            produced = await execute_tts_dispatch(
                dispatch=dispatch, prepared=prepared, sid=sid, emit=emit,
            )
            if produced is not None:
                total_result.produced_media.append(produced)
            return None
        if executor == "stt":
            await execute_stt_dispatch(
                dispatch=dispatch, prepared=prepared, sid=sid, emit=emit,
            )
            return None
        if executor in ("image", "video"):
            # execute_media_dispatch inspects dispatch.output_modalities itself
            # for the concrete modality; pass through as-is.
            produced = await execute_media_dispatch(
                dispatch=dispatch, prepared=prepared, sid=sid, emit=emit,
            )
            if produced is not None:
                total_result.produced_media.append(produced)
            return None
        if executor == "agentic_text":
            return await _execute_agent_dispatch(
                pool, redis,
                dispatch=dispatch,
                prepared=prepared,
                sid=sid,
                tool_soft=tool_soft,
                max_iterations=max_iterations,
                internal_sio=internal_sio,
            )

        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=(
                    f"Unsupported modality pair: in={sorted(dispatch.input_modalities)}, "
                    f"out={sorted(dispatch.output_modalities)}"
                ),
                artifact_type=prepared.artifact_type,
                group_id=str(prepared.group_id),
            ).model_dump(), artifact_type=prepared.artifact_type,
        )
        return None

    # Run all agent dispatches in parallel (enables A/B evals when
    # multiple agents in the winning system handle the same operations)
    with timed("model_call"):
        if len(prepared.dispatches) > 1:
            import asyncio
            agent_results = await asyncio.gather(
                *[_run_one(dispatch) for dispatch in prepared.dispatches],
                return_exceptions=True,
            )
            first_agent_error: BaseException | None = None
            for agent_result in agent_results:
                if isinstance(agent_result, Exception):
                    # S1: a per-agent exception in the parallel fan-out used to
                    # be swallowed (log + continue), yet the run still returned
                    # the OTHER agent's result and the route reported SUCCESS.
                    # The trap: completion is decided by counting persisted
                    # answer rows vs. ``expected_count``. An errored agent never
                    # persists an answer, so the count stays short forever →
                    # ``all_done`` never trips → ``_chat_post_complete`` (attempt
                    # MV refresh + ``attempt.chat_create.completed`` /
                    # ``chat_grade.completed`` lifecycle emits) NEVER fires, while
                    # the HTTP route still 200s. Any consumer keyed on the
                    # attempt lifecycle hangs "in-progress" behind a phantom
                    # success, and the attempt MVs go stale. Capture the error
                    # and re-raise after the loop so the run reaches a real
                    # terminal state: ``runner._run`` emits a single
                    # ``{artifact}.generate.failed`` (carrying run_id) and the
                    # blocking route 5xxs — mirroring the single-agent error
                    # path, never reporting success while skipping the lifecycle.
                    logger.error(f"Agent dispatch failed: {agent_result}")
                    if first_agent_error is None:
                        first_agent_error = agent_result
                    continue
                if agent_result is None:
                    continue
                total_result.total_input_tokens += agent_result.total_input_tokens
                total_result.total_output_tokens += agent_result.total_output_tokens
                total_result.tool_results.extend(agent_result.tool_results)
                total_result.assistant_output = agent_result.assistant_output
                total_result.reasoning_output = agent_result.reasoning_output

            if first_agent_error is not None:
                raise first_agent_error
        elif prepared.dispatches:
            agent_result = await _run_one(prepared.dispatches[0])
            if agent_result is not None:
                total_result.total_input_tokens += agent_result.total_input_tokens
                total_result.total_output_tokens += agent_result.total_output_tokens
                total_result.tool_results.extend(agent_result.tool_results)
                total_result.assistant_output = agent_result.assistant_output
                total_result.reasoning_output = agent_result.reasoning_output

    return total_result


async def _execute_agent_dispatch(
    pool: Any,
    redis: Any,
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    tool_soft: bool = True,
    max_iterations: int,
    internal_sio: Any,
) -> ExecuteGenerationResult:
    """Execute the agentic LLM loop for a single agent dispatch."""
    artifact_type = prepared.artifact_type
    run_id = prepared.run_id
    group_id = prepared.group_id
    session_id = prepared.session_id
    profile_id = prepared.profile_id

    # Register this run so a Stop can target it. ``/attempt/stop`` →
    # ``_cancel(group_id)`` → ``cancel_active_run(group_id)`` looks up
    # ``active_run:{group_id}`` to find the run_id and set a ``cancel_run``
    # marker; the token loop below polls that marker cooperatively. Keyed by
    # group_id to match what stop passes. (setex TTL self-expires; a new run
    # on the same group overwrites — no explicit cleanup needed.)
    try:
        await set_active_run(str(group_id), str(run_id))
    except Exception:
        logger.debug("set_active_run failed for run_id=%s (non-fatal)", run_id)

    # Setup
    messages = format_messages_for_litellm(dispatch.messages)
    llm_config = dispatch.llm_config
    api_key = llm_config.get("api_key")
    tool_choice = llm_config.get("tool_choice", "auto")

    # Build tool lookups
    openai_tools = None
    responses_tools = None
    tool_output_schemas: dict[str, dict[str, str]] = {}
    tool_def_by_name: dict[str, dict[str, Any]] = {}

    if dispatch.tools:
        openai_tools = convert_tools_to_openai_format(dispatch.tools)
        responses_tools = convert_tools_to_responses_format(dispatch.tools)
        tool_output_schemas = build_tool_output_schemas(dispatch.tools)
        for tool_def in dispatch.tools:
            if isinstance(tool_def, dict) and tool_def.get("name"):
                safe_name = sanitize_tool_name(tool_def["name"])
                tool_def_by_name[safe_name] = tool_def

    # Determine API mode
    api_mode = "chat_completions"
    if LITELLM_AVAILABLE and hasattr(litellm, "aresponses"):
        api_mode = "responses"
    logger.info(f"EXECUTE_GEN: api_mode={api_mode}, model={llm_config['model']}, tools={len(dispatch.tools or [])}")

    # Agentic loop state
    chat_messages = list(messages)
    responses_input: list[dict[str, Any]] = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("system", "user", "assistant", "developer")
        and not m.get("tool_calls")
    ]

    # Positive observability — log exactly what's about to be handed
    # to the LLM. Without this we can't tell whether the threaded
    # chat history actually reached the provider or got silently
    # filtered along the way (e.g. the responses_input filter above
    # drops `role: "tool"` and any message carrying `tool_calls`).
    # We log the role sequence plus a short content preview per
    # message — the actual provider call follows immediately, so
    # this is "what OpenAI sees" with very high fidelity.
    def _content_preview(c: Any) -> str:
        if isinstance(c, str):
            return c.replace("\n", " ")[:140]
        if isinstance(c, list):  # multipart blocks
            return f"[{len(c)} blocks]"
        return str(c)[:140] if c is not None else "<None>"
    _outgoing = responses_input if api_mode == "responses" else chat_messages
    logger.info(
        "LLM_CALL run=%s agent=%s api=%s model=%s msgs=%d roles=%s",
        prepared.run_id, dispatch.agent_id, api_mode,
        llm_config.get("model"), len(_outgoing),
        [m.get("role") for m in _outgoing],
    )
    for _i, _m in enumerate(_outgoing):
        logger.info(
            "  [%d] %s: %s",
            _i, _m.get("role"), _content_preview(_m.get("content")),
        )

    total_input_tokens = 0
    total_output_tokens = 0
    all_tool_results: list[dict[str, Any]] = []
    final_assistant_output = ""
    final_reasoning_output = ""
    # Stamped at the moment the first reasoning delta arrives so the
    # persisted ``messages_entry.created_at`` reflects when the model
    # actually started thinking — not when the row was written at
    # run-complete time. The FE pairs this with the assistant row's
    # ``created_at`` to render a real "Thought for Xs" duration.
    final_reasoning_started_at: "datetime | None" = None

    async def _persist_partial_usage_on_cancel() -> None:
        """Flush token/cost + partial text for the iterations that DID complete
        before a Stop landed (G3).

        The Stop raise propagates out of the agentic loop ABOVE the normal
        ``run_complete_impl`` persist, so without this the provider cost already
        consumed by the completed iterations (real input/output tokens) and the
        partial assistant/reasoning text the client already streamed would be
        dropped — under-counted billing + lost history on every cancelled run.
        This records ONLY the usage + partial turn (a plain ``create_token`` +
        ``persist_run_message``), NOT the full ``run_complete_impl``
        coordination: a cancelled run must NOT flip ``all_done`` / fire the
        attempt lifecycle as if it finished. Best-effort — a failure here must
        not mask the cancellation itself, which still re-raises.
        """
        if not (total_input_tokens or total_output_tokens
                or final_assistant_output or final_reasoning_output):
            return
        from app.infra.websocket.persist_run_message import persist_run_message
        from app.tools.entries.tokens.create import create_token
        try:
            async with pool.acquire() as cancel_conn:
                async with cancel_conn.transaction():
                    if final_reasoning_output:
                        await persist_run_message(
                            cancel_conn, redis,
                            run_id=run_id, session_id=session_id,
                            role="assistant", content=final_reasoning_output,
                            reasoning=True,
                            created_at=final_reasoning_started_at,
                            agent_ids=(
                                [dispatch.agent_id] if dispatch.agent_id else None
                            ),
                        )
                    if final_assistant_output:
                        await persist_run_message(
                            cancel_conn, redis,
                            run_id=run_id, session_id=session_id,
                            role="assistant", content=final_assistant_output,
                            agent_ids=(
                                [dispatch.agent_id] if dispatch.agent_id else None
                            ),
                        )
                    if total_input_tokens or total_output_tokens:
                        await create_token(
                            cancel_conn, redis,
                            run_id=run_id, session_id=session_id,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                        )
        except Exception:
            logger.exception(
                "Failed to persist partial usage on cancel for run_id=%s", run_id,
            )

    iteration = 0
    # Tracks whether the loop exited because the model stopped requesting
    # tools (graceful) vs. because it hit ``max_iterations`` still mid-tool-loop
    # (G2 — truncated turn, must be surfaced, not reported as clean success).
    hit_iteration_cap = False
    # H4: the cooperative ``cancel_run:{run_id}`` marker is set with a 300s TTL
    # and used to be left behind, so a run_id reused within that window (the
    # grading pipeline / a client-supplied ``client_run_id``) would have its
    # very first cancel-poll instant-kill it — a run nobody stopped. Delete the
    # marker on EVERY exit (success, cancel, error) so it can't leak across
    # runs. ``remove_active_run`` (previously dead code) is wired up here too to
    # clear the ``active_run:{group_id}`` pointer in the same breath.
    try:
        while iteration < max_iterations:
            iteration += 1

            # Iteration-boundary cancellation check (G1). The in-stream poll below
            # only fires every ~12 events, so a tool-heavy iteration (a short
            # stream of ~5 events) would never reach it — Stop would be a no-op for
            # exactly the turns users most want to abort, and the loop would issue
            # the NEXT provider call + dispatch more tools after Stop. Checking the
            # ``cancel_run`` marker once per iteration (one Redis EXISTS) makes Stop
            # reliable regardless of stream length, before any further model cost or
            # tool dispatch is incurred.
            if await is_run_cancelled(str(run_id)):
                raise _GenerationCancelled(_CANCEL_MESSAGE)

            # Call LLM
            try:
                if api_mode == "responses":
                    stream = await _call_responses_api(
                        model=llm_config["model"],
                        responses_input=responses_input,
                        tools=responses_tools,
                        tool_choice=tool_choice,
                        api_key=api_key,
                        base_url=llm_config.get("base_url"),
                        temperature=llm_config.get("temperature") or 0.0,
                        extra_body=None,
                    )
                else:
                    stream = await _call_chat_completions_api(
                        model=llm_config["model"],
                        messages=chat_messages,
                        tools=openai_tools,
                        tool_choice=tool_choice,
                        api_key=api_key,
                        base_url=llm_config.get("base_url"),
                        temperature=llm_config.get("temperature") or 0.0,
                        reasoning=llm_config.get("reasoning"),
                        extra_body=None,
                    )
            except Exception as e:
                if api_mode == "responses":
                    logger.warning(f"Responses API failed, falling back to Chat Completions: {e}")
                    api_mode = "chat_completions"
                    stream = await _call_chat_completions_api(
                        model=llm_config["model"],
                        messages=chat_messages,
                        tools=openai_tools,
                        tool_choice=tool_choice,
                        api_key=api_key,
                        base_url=llm_config.get("base_url"),
                        temperature=llm_config.get("temperature") or 0.0,
                        reasoning=llm_config.get("reasoning"),
                        extra_body=None,
                    )
                else:
                    raise

            # Process stream events
            assistant_output = ""
            reasoning_output = ""
            input_tokens = 0
            output_tokens = 0
            tool_call_states: dict[str, dict[str, Any]] = {}
            tool_results: list[dict[str, Any]] = []
            output_items: list[dict[str, Any]] = []

            cancel_poll = 0
            async for event in stream_litellm_events(stream):
                # Cooperative cancellation: poll the Stop marker periodically
                # (every ~12 events — a redis hit per token would be wasteful).
                # ``/attempt/stop`` sets ``cancel_run:{run_id}`` via the
                # ``active_run:{group_id}`` registered above. Raising here
                # propagates to runner._run's except, which emits
                # ``{artifact}.generate.failed`` (carrying run_id) → the watcher
                # sees its terminal frame and the streaming reply truncates cleanly.
                cancel_poll += 1
                if cancel_poll % 12 == 0 and await is_run_cancelled(str(run_id)):
                    raise _GenerationCancelled(_CANCEL_MESSAGE)
                event_type = event.get("type")

                if event_type == "text_delta":
                    delta = event.get("delta", "")
                    if delta:
                        assistant_output += delta
                        await internal_sio.emit(
                            f"{artifact_type}.generate.text.progress",
                            {
                                "sid": sid,
                                "rooms": [str(profile_id)],
                                "artifact_type": artifact_type,
                                "run_id": str(run_id),
                                "group_id": str(group_id),
                                "agent_id": str(dispatch.agent_id),
                                "delta": delta,
                            },
                        )

                elif event_type == "text_complete":
                    assistant_output = event.get("text", assistant_output)
                    await internal_sio.emit(
                        f"{artifact_type}.generate.text.complete",
                        {
                            "sid": sid,
                            "rooms": [str(profile_id)],
                            "artifact_type": artifact_type,
                            "run_id": str(run_id),
                            "group_id": str(group_id),
                            "role": "assistant",
                            "text": assistant_output,
                        },
                    )

                elif event_type == "reasoning_delta":
                    # Chain-of-thought channel. Accumulated separately from
                    # assistant_output so we can persist it as a distinct
                    # ``messages_entry`` row with reasoning=True. As of vLLM
                    # 0.19.0+nv26.04 these events do not fire — Gemma 4's
                    # <|channel>thought blocks leak into the regular text
                    # stream (vLLM issue #38855). Handler is wired up so
                    # reasoning will start persisting automatically once
                    # upstream emits a proper channel.
                    delta = event.get("delta", "")
                    if delta:
                        if final_reasoning_started_at is None:
                            final_reasoning_started_at = datetime.now(UTC)
                        reasoning_output += delta
                        await internal_sio.emit(
                            f"{artifact_type}.generate.reasoning.progress",
                            {
                                "sid": sid,
                                "rooms": [str(profile_id)],
                                "artifact_type": artifact_type,
                                "run_id": str(run_id),
                                "group_id": str(group_id),
                                "agent_id": str(dispatch.agent_id),
                                "delta": delta,
                            },
                        )

                elif event_type == "reasoning_complete":
                    reasoning_output = event.get("text", reasoning_output)
                    await internal_sio.emit(
                        f"{artifact_type}.generate.reasoning.complete",
                        {
                            "sid": sid,
                            "rooms": [str(profile_id)],
                            "artifact_type": artifact_type,
                            "run_id": str(run_id),
                            "group_id": str(group_id),
                            "role": "assistant",
                            "text": reasoning_output,
                        },
                    )

                elif event_type in ("tool_call_start", "tool_call_delta"):
                    raw_id = cast(str, event.get("tool_call_id"))
                    tool_call_id = (
                        raw_id[:40] if api_mode == "chat_completions" and len(raw_id) > 40
                        else raw_id
                    )
                    st = tool_call_states.setdefault(
                        tool_call_id,
                        {
                            "raw_id": raw_id,
                            "responses_call_id": event.get("responses_call_id") or raw_id,
                            "tool_call_id": tool_call_id,
                            "tool_name": event.get("tool_name"),
                            "arguments": "",
                            # Pre-mint the DB call row id now so every downstream
                            # event — progress, audit .started/.completed — shares
                            # the same handle. create_call will reuse this id.
                            "call_id": uuid.uuid4(),
                        },
                    )
                    if event_type == "tool_call_start":
                        await internal_sio.emit(
                            f"{artifact_type}.generate.call.start",
                            {
                                "sid": sid,
                                "rooms": [str(profile_id)],
                                "artifact_type": artifact_type,
                                "run_id": str(run_id),
                                "group_id": str(group_id),
                                # ``call_id`` carries the pre-minted DB row id so
                                # the audit lifecycle (``{artifact}.{op}.started``)
                                # and this pipeline event share one handle on the
                                # client — natural dedup keys to one bubble per
                                # logical tool call. ``tool_call_id`` stays as
                                # the provider's own string id for provenance.
                                "call_id": str(st["call_id"]),
                                "tool_call_id": tool_call_id,
                                "tool_name": st.get("tool_name"),
                            },
                        )
                        # ``{artifact}.{op}.started`` is now emitted by the
                        # audit framework (``run_artifact_operation_with_audit``)
                        # once args are parsed and the impl is about to run.
                        # The audit emit carries the ``tool`` envelope,
                        # ``operation_key``, etc. — a richer payload than this
                        # pre-args pipeline emit could produce. Firing here
                        # too produced duplicate ``<artifact>.<op>.started``
                        # events on the wire (same ``call_id``, deduped to one
                        # bubble client-side, but visible noise in the SSE
                        # log). Single source of truth: the audit framework.
                    if event_type == "tool_call_delta":
                        delta = event.get("delta", "") or ""
                        if event.get("tool_name") and not st["tool_name"]:
                            st["tool_name"] = event["tool_name"]
                        st["arguments"] += delta

                        # Per-tool progress event: if the tool resolves to a
                        # single (artifact, operation) pair, emit a scoped
                        # ``{artifact}.{operation}.progress`` event carrying
                        # the *parsed* partial args so consumers can read
                        # fields (e.g. ``text``) directly. Multi-op tools
                        # skip this emit (op isn't known until finalize).
                        route = _resolve_tool_route(
                            tool_def_by_name.get(st.get("tool_name") or "")
                        )
                        if route is not None:
                            route_artifact, route_op = route
                            parsed_args = parse_partial_json(st["arguments"]) or {}
                            await internal_sio.emit(
                                f"{route_artifact}.{route_op}.progress",
                                {
                                    "sid": sid,
                                    "rooms": [str(profile_id)],
                                    "artifact_type": artifact_type,
                                    "run_id": str(run_id),
                                    "group_id": str(group_id),
                                    # ``call_id`` is the unified handle across
                                    # streaming progress and audit .started/
                                    # .completed. Provider ``tool_call_id`` is
                                    # server-internal (kept on tool_call_states)
                                    # and not exposed to the client.
                                    "call_id": str(st["call_id"]),
                                    "tool_name": st.get("tool_name"),
                                    "arguments": parsed_args,
                                    "delta": delta,
                                    # Unpack args to top-level so consumers read
                                    # ``data.text`` / ``data.chat_id`` directly,
                                    # matching the audit .started/.completed shape.
                                    **{k: v for k, v in parsed_args.items() if isinstance(k, str)},
                                },
                            )

                elif event_type == "tool_call_complete":
                    raw_id = cast(str, event.get("tool_call_id"))
                    tool_call_id = (
                        raw_id[:40] if api_mode == "chat_completions" and len(raw_id) > 40
                        else raw_id
                    )
                    tool_name = (
                        event.get("name")
                        or tool_call_states.get(tool_call_id, {}).get("tool_name")
                        or ""
                    )
                    st = tool_call_states.get(tool_call_id, {})
                    arguments_str = event.get("arguments") or st.get("arguments", "")

                    try:
                        arguments_dict = json.loads(arguments_str) if arguments_str else {}
                    except json.JSONDecodeError:
                        arguments_dict = {}

                    # Execute tool via infra path (audit emits artifact events).
                    # call_success tracks the structured outcome separately from
                    # the LLM-facing string so a templated render (markdown / plain
                    # text, not valid JSON) doesn't get re-parsed and falsely
                    # downgraded to success=False on the WS emit.
                    td = tool_def_by_name.get(tool_name)
                    call_success: bool

                    # Eval runs dispatch live (no replay tape). The
                    # ``soft=True`` + ``eval=True`` flags on InfraContext
                    # below stage every write as dormant + tag the
                    # soft_calls ledger so the UI filters eval entries
                    # out of normal listings.
                    if not td:
                        tool_result_str = json.dumps({
                            "success": False,
                            "message": f"Tool not found: {tool_name}",
                        })
                        call_success = False
                    else:
                        # Pre-dispatch cancellation check (G1). A tool-heavy turn
                        # can emit several tool_call_complete events inside one
                        # short stream; honour Stop before dispatching each tool so
                        # a Stop arriving mid-turn doesn't run further (possibly
                        # write-staging) tool operations.
                        if await is_run_cancelled(str(run_id)):
                            raise _GenerationCancelled(_CANCEL_MESSAGE)
                        try:
                            spec = resolve_tool_spec(td, arguments_dict)
                            ctx = InfraContext(
                                pool=pool,
                                redis=redis,
                                profile_id=profile_id,
                                session_id=session_id,
                                group_id=group_id,
                                run_id=run_id,
                                sid=sid,
                                soft=tool_soft,
                                eval=prepared.eval,
                                operation_key=uuid.uuid4(),
                                instruction_template=td.get("_instruction_template"),
                                call_id=st.get("call_id"),
                            )
                            results = await execute_infra_operation(ctx, spec)
                            # Layer 3 output render — shared with MCP dispatch.
                            from app.infra.tools.render_result import (
                                render_tool_result_with_meta,
                            )

                            meta = render_tool_result_with_meta(td, results)
                            tool_result_str = meta.rendered
                            call_success = meta.success
                        except Exception as e:
                            tool_result_str = json.dumps({
                                "success": False,
                                "message": str(e),
                            })
                            call_success = False

                    try:
                        tool_result = json.loads(tool_result_str)
                    except json.JSONDecodeError:
                        # Rendered template output is plain text/markdown — not a
                        # parse failure of a real JSON payload. Preserve the true
                        # call_success here; the dict shape is only kept around so
                        # downstream code that expects ``result`` as a dict (e.g.
                        # the Responses-API tool_result feedback) still works.
                        tool_result = {"success": call_success, "message": tool_result_str}

                    tool_results.append({
                        "tool_call_id": tool_call_id,
                        "raw_id": raw_id,
                        "responses_call_id": st.get("responses_call_id", raw_id),
                        "tool_name": tool_name,
                        "arguments": arguments_dict,
                        "arguments_str": arguments_str,
                        "result": tool_result,
                        "result_str": tool_result_str,
                        # Server-side ``calls_entry.id`` for this tool dispatch —
                        # used as ``idempotency_key`` by the FE to promote/reject
                        # the soft write via ``/<artifact>/create``.
                        "call_id": str(st["call_id"]) if st.get("call_id") else None,
                    })

                    # Emit call complete — use the structured success state from
                    # render_tool_result_with_meta, NOT the parsed string. Templated
                    # renders return markdown/plain-text that's not JSON, so the
                    # legacy `tool_result.get("success")` path was reading the
                    # JSONDecodeError fallback and emitting success=False for
                    # every templated tool, even on healthy runs.
                    await internal_sio.emit(
                        f"{artifact_type}.generate.call.complete",
                        {
                            "sid": sid,
                            "rooms": [str(profile_id)],
                            "artifact_type": artifact_type,
                            "run_id": str(run_id),
                            "group_id": str(group_id),
                            # See ``generate.call.start`` for the ``call_id`` rationale —
                            # same pre-minted DB row id, used for client-side dedup
                            # against the audit lifecycle.
                            "call_id": str(st["call_id"]) if st.get("call_id") else None,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "success": call_success,
                        },
                    )

                elif event_type == "output_item":
                    item = event.get("item")
                    if item:
                        output_items.append(item)

                elif event_type == "message_complete":
                    usage_data = event.get("usage")
                    if isinstance(usage_data, dict):
                        input_tokens = usage_data.get("prompt_tokens", 0) or 0
                        output_tokens = usage_data.get("completion_tokens", 0) or 0

            # End of stream

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            all_tool_results.extend(tool_results)
            final_assistant_output = assistant_output
            final_reasoning_output = reasoning_output

            if not tool_results:
                break

            # The model still wants to call tools but we've reached the iteration
            # cap → the turn is being truncated mid-tool-loop (G2). Flag it so the
            # post-loop code surfaces an explicit terminal state instead of
            # persisting/reporting whatever partial (often empty) ``final_assistant_output``
            # the last tool-only iteration left as a clean success.
            if iteration >= max_iterations:
                hit_iteration_cap = True
                break

            # Update conversation state for next iteration
            if api_mode == "responses":
                for item in output_items:
                    # Defensive filter: vLLM 0.19's Responses API rejects
                    # bare assistant messages with empty output_text content
                    # (no union variant matches — see stream_litellm_events
                    # comment). Should already be skipped at emit time, but
                    # keep the check here so a stray item from any other
                    # source can't 400 the whole next iteration.
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "message"
                        and item.get("role") == "assistant"
                    ):
                        content = item.get("content") or []
                        has_text = any(
                            isinstance(c, dict)
                            and c.get("type") in ("output_text", "input_text")
                            and (c.get("text") or "").strip()
                            for c in content
                        )
                        if not has_text:
                            continue
                    responses_input.append(item)
                for tr in tool_results:
                    responses_input.append({
                        "type": "function_call_output",
                        "call_id": tr.get("responses_call_id", tr["raw_id"]),
                        "output": tr["result_str"],
                    })
            else:
                assistant_tool_calls = [
                    {
                        "id": tr["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": tr["tool_name"],
                            "arguments": tr["arguments_str"],
                        },
                    }
                    for tr in tool_results
                ]
                chat_messages.append({
                    "role": "assistant",
                    "content": assistant_output or "",
                    "tool_calls": assistant_tool_calls,
                })
                for tr in tool_results:
                    chat_messages.append({
                        "tool_call_id": tr["tool_call_id"],
                        "role": "tool",
                        "name": tr["tool_name"],
                        "content": tr["result_str"],
                    })

            if tool_choice == "required":
                tool_choice = "auto"

        # Max-iterations terminal state (G2). The loop fell through the cap while
        # the model was still requesting tools, so it never produced a closing
        # answer this turn — ``final_assistant_output`` is whatever the last
        # tool-only iteration left, typically "". Surfacing this matters: without
        # it ``run_complete_impl`` skips the empty assistant row (``if
        # assistant_output``) and the route returns a clean 200, so the user sees
        # an empty reply with no signal the loop was capped. Make it terminal:
        #   - no usable answer  → raise, so ``runner._run`` emits
        #     ``{artifact}.generate.failed`` (a clear terminal frame the watcher
        #     sees) rather than a silent empty-success turn.
        #   - partial answer    → keep it but prepend an explicit truncation notice
        #     so it is never presented as a normal, complete reply.
        if hit_iteration_cap:
            logger.warning(
                "Agentic loop hit max_iterations=%d for run_id=%s agent=%s "
                "(model still requesting tools) — surfacing truncation",
                max_iterations, run_id, dispatch.agent_id,
            )
            if not final_assistant_output.strip():
                raise RuntimeError(
                    f"Generation stopped: reached the maximum of {max_iterations} "
                    "tool-use iterations without a final answer."
                )
            final_assistant_output = (
                f"[Note: stopped after the maximum of {max_iterations} tool-use "
                "iterations; this answer may be incomplete.]\n\n"
                f"{final_assistant_output}"
            )

        # Per-agent completion event — fires once per agent inside the
        # shared run. Lets the FE start grading / promoting a single
        # candidate before the full pool finishes. Carries this agent's
        # eval slot when the agent was rubric-bearing.
        invocation_slot = None
        if prepared.eval_setup is not None:
            for slot in prepared.eval_setup.invocations:
                if slot.agent_id == dispatch.agent_id:
                    invocation_slot = slot
                    break

        dispatch_total = len(prepared.dispatches)
        dispatch_index = next(
            (i for i, d in enumerate(prepared.dispatches) if d.agent_id == dispatch.agent_id),
            0,
        )

        # Pull this agent's soft-write call_ids straight off ``all_tool_results``.
        # Each entry's ``call_id`` is the ``calls_entry.id`` minted at dispatch
        # time, which doubles as the ``idempotency_key`` the FE uses to
        # promote/reject via ``/<artifact>/create``.
        agent_call_ids = [
            tr["call_id"] for tr in all_tool_results if tr.get("call_id")
        ]

        await internal_sio.emit(
            f"{artifact_type}.generate.agent_completed",
            {
                "sid": sid,
                "rooms": [str(profile_id)],
                "artifact_type": artifact_type,
                "run_id": str(run_id),
                "group_id": str(group_id),
                "agent_id": str(dispatch.agent_id),
                "test_id": (
                    str(prepared.eval_setup.test_id)
                    if prepared.eval_setup is not None
                    else None
                ),
                "invocation": invocation_slot.model_dump(mode="json")
                if invocation_slot is not None
                else None,
                "call_ids": agent_call_ids,
                "progress": {
                    "index": dispatch_index,
                    "total": dispatch_total,
                },
            },
        )

        # Finalize: persist assistant text + tokens, run multi-agent coordination
        # then emit the final completion channel.
        # ``run_complete_impl`` is called directly (not via an internal event)
        # so nothing top-level needs to exist to carry the workflow.
        from app.infra.globals import UPLOAD_FOLDER
        from app.infra.websocket.run_complete_impl import run_complete_impl

        run_complete_payload: dict[str, Any] = {
            "sid": sid,
            "run_id": str(run_id),
            "group_id": str(group_id),
            "session_id": str(session_id),
            "profile_id": str(profile_id),
            "profiles_id": str(prepared.profiles_id),
            # Dispatching agent (H2). Attribute the persisted assistant +
            # reasoning rows to THIS agent so a multi-agent run's next turn
            # can scope each agent's history to its own turns (see
            # fetch_group_history) instead of pulling every agent's replies.
            "agent_id": str(dispatch.agent_id) if dispatch.agent_id else None,
            "artifact_type": artifact_type,
            "modality": "text",
            "input_text_tokens": total_input_tokens,
            "output_text_tokens": total_output_tokens,
            "assistant_output": final_assistant_output,
            "reasoning_output": final_reasoning_output,
            "reasoning_started_at": (
                final_reasoning_started_at.isoformat()
                if final_reasoning_started_at is not None
                else None
            ),
            "tool_results": all_tool_results,
            "metadata": dispatch.metadata or {},
        }
        # ``run_complete_impl`` persists the load-bearing turn (assistant text +
        # reasoning + token/cost row) before any post-persist emits. It now re-raises
        # on a turn-persist failure (post-persist emit failures stay swallowed inside
        # ``_chat_post_complete``). Do NOT swallow-and-return a populated result here:
        # that would report the run complete (route 200s) while the DB is missing the
        # turn + usage — lost history and undercounted billing surfaced as success
        # (E1). Let it propagate to ``runner._run``, which emits
        # ``{artifact}.generate.failed`` so the failure is visible.
        async with pool.acquire() as conn:
            await run_complete_impl(
                run_complete_payload,
                emit=make_emit(),
                conn=conn,
                redis=redis,
                upload_folder=UPLOAD_FOLDER,
            )

        return ExecuteGenerationResult(
            run_id=run_id,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            tool_results=all_tool_results,
            assistant_output=final_assistant_output,
            reasoning_output=final_reasoning_output,
        )
    except _GenerationCancelled:
        # Stop landed mid-loop. Flush the usage + partial text the
        # completed iterations produced (G3) BEFORE re-raising, so billing
        # and history aren't silently dropped. Re-raise unchanged so
        # ``runner._run`` still emits ``{artifact}.generate.failed`` and the
        # route surfaces the cancellation.
        await _persist_partial_usage_on_cancel()
        raise
    finally:
        # Always clear the cancel marker + active-run pointer (H4) so a
        # reused run_id within the 300s TTL isn't instant-killed by a stale
        # Stop nobody pressed. Best-effort — never mask the real result.
        try:
            await redis.delete(f"cancel_run:{run_id}")
        except Exception:
            logger.debug("cancel_run marker cleanup failed for run_id=%s", run_id)
        try:
            from app.infra.websocket.remove_active_run import remove_active_run
            await remove_active_run(str(group_id), redis_client=redis)
        except Exception:
            logger.debug("active_run cleanup failed for group_id=%s", group_id)
