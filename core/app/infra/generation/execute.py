"""Generation execute — deterministic infra function.

Runs the agentic LLM loop for text + tool call modality.
Extracted from generate_artifact_impl — uses the same proven LLM
streaming and tool execution patterns.

Events emitted are artifact-scoped:
  {artifact_type}.generate.progress — text/tool streaming
  Tool calls go through execute_infra_operation → audit path
  emits {artifact}.{operation}.completed naturally.

No generic events (generate_text_progress, generate_call_complete, etc.).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from app.infra.artifacts import (
    convert_tools_to_openai_format,
    convert_tools_to_responses_format,
    format_messages_for_litellm,
    stream_litellm_events,
)
from app.infra.artifacts.convert_tools_to_openai_format import sanitize_tool_name
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import get_internal_sio
from app.infra.tools.execute_infra_operation import (
    InfraContext,
    execute_infra_operation,
)
from app.infra.tools.resolve_tool_spec import resolve_tool_spec
from app.infra.websocket.socket_event import internal_event
from app.infra.websocket.tool_call_utils import (
    build_tool_output_schemas,
    parse_partial_json,
    resolve_output_fields,
)
from app.utils.auth.decrypt_api_key import decrypt_api_key

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# LLM API calls (extracted from generate_artifact_impl)
# ---------------------------------------------------------------------------


async def _call_responses_api(
    *, model: str, responses_input: list, tools: list | None,
    tool_choice: str, api_key: str | None, base_url: str | None,
    temperature: float, extra_body: dict | None,
) -> Any:
    """Call litellm Responses API."""
    # The openai/ prefix tells litellm SDK to use OpenAI-compatible protocol.
    effective_model = f"openai/{model}" if base_url and "/" not in model else model
    kwargs: dict[str, Any] = {
        "model": effective_model,
        "input": responses_input,
        "stream": True,
        "temperature": temperature,
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
    artifact_type = prepared.artifact_type
    run_id = prepared.run_id

    total_result = ExecuteGenerationResult(run_id=run_id)

    for dispatch in prepared.dispatches:
        agent_result = await _execute_agent_dispatch(
            pool, redis,
            dispatch=dispatch,
            prepared=prepared,
            sid=sid,
            tool_soft=tool_soft,
            max_iterations=max_iterations,
            internal_sio=internal_sio,
        )

        total_result.total_input_tokens += agent_result.total_input_tokens
        total_result.total_output_tokens += agent_result.total_output_tokens
        total_result.tool_results.extend(agent_result.tool_results)
        total_result.assistant_output = agent_result.assistant_output

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

    # Agentic loop state
    chat_messages = list(messages)
    responses_input: list[dict[str, Any]] = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("system", "user", "assistant", "developer")
        and not m.get("tool_calls")
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    all_tool_results: list[dict[str, Any]] = []
    final_assistant_output = ""

    iteration = 0
    while iteration < max_iterations:
        iteration += 1

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
        input_tokens = 0
        output_tokens = 0
        tool_call_states: dict[str, dict[str, Any]] = {}
        tool_results: list[dict[str, Any]] = []
        output_items: list[dict[str, Any]] = []

        async for event in stream_litellm_events(stream):
            event_type = event.get("type")

            if event_type == "text_delta":
                delta = event.get("delta", "")
                if delta:
                    assistant_output += delta
                    await internal_sio.emit(
                        f"{artifact_type}.generate.text.progress",
                        {
                            "sid": sid,
                            "rooms": [sid] if sid else [],
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
                        "rooms": [sid] if sid else [],
                        "artifact_type": artifact_type,
                        "run_id": str(run_id),
                        "group_id": str(group_id),
                        "text": assistant_output,
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
                    },
                )
                if event_type == "tool_call_start":
                    await internal_sio.emit(
                        f"{artifact_type}.generate.call.start",
                        {
                            "sid": sid,
                            "rooms": [sid] if sid else [],
                            "artifact_type": artifact_type,
                            "run_id": str(run_id),
                            "group_id": str(group_id),
                            "tool_call_id": tool_call_id,
                            "tool_name": st.get("tool_name"),
                        },
                    )
                if event_type == "tool_call_delta":
                    delta = event.get("delta", "") or ""
                    if event.get("tool_name") and not st["tool_name"]:
                        st["tool_name"] = event["tool_name"]
                    st["arguments"] += delta

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

                # Execute tool via infra path (audit emits artifact events)
                td = tool_def_by_name.get(tool_name)
                if not td:
                    tool_result_str = json.dumps({
                        "success": False,
                        "message": f"Tool not found: {tool_name}",
                    })
                else:
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
                            operation_key=uuid.uuid4(),
                            instruction_template=td.get("_instruction_template"),
                        )
                        results = await execute_infra_operation(ctx, spec)
                        tool_result_str = json.dumps({
                            "success": all(r.success for r in results),
                            "results": [r.model_dump(mode="json") for r in results],
                        })
                    except Exception as e:
                        tool_result_str = json.dumps({
                            "success": False,
                            "message": str(e),
                        })

                try:
                    tool_result = json.loads(tool_result_str)
                except json.JSONDecodeError:
                    tool_result = {"success": False, "message": tool_result_str}

                # Render template (Layer 3) if available
                response_template = td.get("_instruction_template") if td else None
                if response_template and isinstance(tool_result, dict):
                    try:
                        from jinja2 import Environment, Undefined
                        env = Environment(undefined=Undefined)
                        tmpl = env.from_string(response_template)
                        template_ctx = {**tool_result, "result": tool_result}
                        rendered = tmpl.render(**template_ctx).strip()
                        if rendered:
                            tool_result_str = rendered
                    except Exception:
                        pass

                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "raw_id": raw_id,
                    "responses_call_id": st.get("responses_call_id", raw_id),
                    "tool_name": tool_name,
                    "arguments": arguments_dict,
                    "arguments_str": arguments_str,
                    "result": tool_result,
                    "result_str": tool_result_str,
                })

                # Emit call complete
                await internal_sio.emit(
                    f"{artifact_type}.generate.call.complete",
                    {
                        "sid": sid,
                        "rooms": [sid] if sid else [],
                        "artifact_type": artifact_type,
                        "run_id": str(run_id),
                        "group_id": str(group_id),
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "success": tool_result.get("success", False) if isinstance(tool_result, dict) else False,
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

        if not tool_results:
            break

        # Update conversation state for next iteration
        if api_mode == "responses":
            for item in output_items:
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

    return ExecuteGenerationResult(
        run_id=run_id,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        tool_results=all_tool_results,
        assistant_output=final_assistant_output,
    )
