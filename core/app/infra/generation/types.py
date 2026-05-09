"""Generation infrastructure types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


def _default_output_modalities() -> set[str]:
    return {"text", "call"}


def _default_input_modalities() -> set[str]:
    return {"text"}


@dataclass
class AgentDispatch:
    """Everything needed to execute one agent's LLM loop."""

    agent_id: UUID
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    llm_config: dict[str, Any]
    resource_types: list[str]
    metadata: dict[str, Any] | None = None
    developer_instruction_templates: list[str] | None = None
    # Modality pair used by the unified dispatcher. See execute.py for the
    # (input, output) → executor rules. Defaults describe a text agentic loop
    # with tool calls enabled ("call" is load-bearing — it signals tool use).
    input_modalities: set[str] = field(default_factory=_default_input_modalities)
    output_modalities: set[str] = field(default_factory=_default_output_modalities)
    # Audio / realtime passthrough
    chat_id: str | None = None
    conversation_id: str | None = None
    audios_id: str | None = None
    # Media passthrough (pre-uploaded assets or AI output)
    file_path: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    upload_id: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True)
class ReplayTapeEntry:
    """One historical tool call in a benchmark replay tape.

    During a trace-driven benchmark run, the LLM dispatches against a
    pre-loaded tape of historical tool outputs. When the LLM calls a
    tool resolving to ``(artifact, operation)``, the dispatch loop
    returns the next unconsumed entry matching that pair —
    substituting the historical raw_output bytes verbatim, regardless
    of args or which specific tool the LLM picked. The impl is never
    invoked, no rows are written anywhere, no soft_calls ledger
    pending entries pollute the user's UI. Pure tape playback.

    Permission-keyed (not tool_id-keyed) so the user can swap a
    historical tool for a different one granting the same
    (artifact, operation). Same canned output is served either way,
    keeping benchmarks reproducible while still letting users vary
    tool definitions to test how naming/description affects model
    behavior.

    Consumption is per-permission: calls resolving to (persona, search)
    consume entries with that pair in chronological order; other
    permissions' entries are independent.
    """

    artifact: str  # canonical permission artifact ("persona", "scenario", ...)
    operation: str  # canonical permission operation ("create", "search", ...)
    operation_key: UUID
    historical_call_id: UUID
    historical_tool_id: UUID  # for traceability / debugging
    raw_output: Any  # parsed JSON, typically a dict


@dataclass
class PrepareGenerationResult:
    """Full preparation result — ready to execute on a moment's notice."""

    run_id: UUID
    group_id: UUID
    session_id: UUID
    profile_id: UUID
    profiles_id: UUID
    artifact_type: str
    dispatches: list[AgentDispatch] = field(default_factory=list)
    test_id: UUID | None = None
    resource_types: list[str] = field(default_factory=list)
    # Set when the run was prepared from a benchmark trace (trace_id
    # → historical_run_id). The execute loop reads this to substitute
    # tool outputs from the tape instead of running impls. None for
    # non-replay runs (the standard path).
    replay_tape: list[ReplayTapeEntry] | None = None
