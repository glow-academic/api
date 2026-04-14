"""Generation infrastructure types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


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
