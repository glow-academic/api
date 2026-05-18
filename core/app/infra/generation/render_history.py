"""Modality-aware rendering of historical messages for one dispatch.

Each dispatched agent has its own ``input_modalities`` set (resolved
from the model's modality junction in tool_graph). This module decides,
per-message, how to feed history back to that agent's LLM:

  * User-typed text                      → plain text
  * User-driven audited tool call        → plain text (rendered Jinja
                                            output) — OpenAI schema
                                            disallows tool_calls on
                                            role="user", so this is
                                            forced regardless of the
                                            agent's modalities.
  * Assistant text response              → plain text
  * Assistant tool call (call ∈ in_mods) → OpenAI tool_calls format:
                                            {role: assistant,
                                             content: null,
                                             tool_calls: [...]}
                                            + matching {role: tool,
                                                       tool_call_id,
                                                       content: <result>}
  * Assistant tool call (call ∉ in_mods) → plain text fallback

Image / audio / video attached to historical messages are NOT yet
threaded — same machinery (modality-filtered content blocks) applies
when we extend this; today's surface is text + call only.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.infra.generation.chat_history import HistoryMessage, HistoryToolCall


def _build_tool_name_lookup(
    scoped_tools: list[dict[str, Any]],
) -> dict[UUID, str]:
    """Index ``{tool_id: tool_name}`` from the dispatch's scoped tool
    dicts. ``id`` and ``name`` are the canonical fields on each tool
    dict — same shape passed to the LLM."""
    out: dict[UUID, str] = {}
    for td in scoped_tools:
        tid_raw = td.get("id")
        name = td.get("name")
        if not tid_raw or not name:
            continue
        try:
            out[UUID(str(tid_raw))] = str(name)
        except (ValueError, TypeError):
            continue
    return out


def _tool_name(
    name_by_id: dict[UUID, str], tool_call: HistoryToolCall
) -> str:
    """Resolve a call's tool_id to its display name. Falls back to
    ``"tool_call"`` when the tool is no longer scoped to this dispatch
    (e.g. retired between runs, or the historical tool isn't part of
    the current agent's surface)."""
    if tool_call.tool_id is None:
        return "tool_call"
    return name_by_id.get(tool_call.tool_id, "tool_call")


def render_history_for_dispatch(
    history: list[HistoryMessage],
    *,
    input_modalities: set[str] | frozenset[str],
    scoped_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Render group history into LLM-ready messages for one agent.

    Output is a flat list of OpenAI-shaped messages, ready to splice
    between the system+developer framing and the current user
    instruction in ``prepare.py``.
    """
    supports_calls = "call" in input_modalities
    name_by_id = _build_tool_name_lookup(scoped_tools)
    out: list[dict[str, Any]] = []

    for msg in history:
        # User: always plain text. The persisted body is either the
        # user's typed input or the Jinja-rendered output of an
        # audited operation they triggered. Both are the right thing
        # to put in `content` here.
        if msg.role == "user":
            if msg.text:
                out.append({"role": "user", "content": msg.text})
            continue

        # Assistant text-only (no audited tool calls) — straightforward.
        if not msg.tool_calls:
            if msg.text:
                out.append({"role": "assistant", "content": msg.text})
            continue

        # Assistant + tool calls + agent supports the `call` input
        # modality → OpenAI tool_calls format. Each call becomes both
        # an entry in the assistant's `tool_calls` array AND a
        # follow-up `tool` role message carrying the result text.
        if supports_calls:
            tool_calls_payload = [
                {
                    "id": str(tc.call_id),
                    "type": "function",
                    "function": {
                        "name": _tool_name(name_by_id, tc),
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in msg.tool_calls
            ]
            out.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls_payload,
                }
            )
            # Result text — the Jinja-rendered output. We attach it to
            # the LAST tool_call_id; if there were multiple calls in
            # one persisted message, all share this body. Future work:
            # split the persisted text per-call if it ever becomes
            # multi-block.
            if msg.text and tool_calls_payload:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_calls_payload[-1]["id"],
                        "content": msg.text,
                    }
                )
            continue

        # Assistant + tool calls + agent does NOT support `call` input →
        # plain text fallback. The Jinja-rendered text already
        # describes what was done and what came back, so the model
        # still gets useful context — just without the structured
        # call boundary.
        if msg.text:
            out.append({"role": "assistant", "content": msg.text})

    return out
