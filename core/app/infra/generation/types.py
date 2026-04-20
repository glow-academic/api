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
