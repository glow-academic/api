"""Shared return types for infra test factories."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProfileIdentityFixture:
    artifact_id: UUID
    profile_resource_id: UUID
    name: str | None
    role: str | None
    role_name: str | None
    role_description: str | None
    role_artifacts: list[str]
    departments: list[str]
    emails: list[str]


@dataclass(frozen=True)
class SettingGraphFixture:
    profile_artifact_id: UUID
    profile_resource_id: UUID
    department_id: UUID
    setting_id: UUID
    system_id: UUID
    agent_id: UUID
    tool_id: UUID
    operation: str
    resources: list[str]
    entries: list[str]
    artifacts: list[str]


@dataclass(frozen=True)
class SystemGraphFixture:
    system_id: UUID
    agent_id: UUID
    model_id: UUID
    provider_id: UUID
    tool_id: UUID
    arg_id: UUID
    arg_output_id: UUID
    prompt_id: UUID
    instruction_id: UUID
    rubric_id: UUID


@dataclass(frozen=True)
class PersonaContextFixture:
    persona_id: UUID
    group_id: UUID
    draft_id: UUID
    published_name_id: UUID
    published_name: str
    draft_name_id: UUID
    draft_name: str
    selected_description_id: UUID
    selected_description: str
    suggestion_description_id: UUID
    suggestion_description: str
    persona_flag_id: UUID
    scenario_flag_id: UUID
