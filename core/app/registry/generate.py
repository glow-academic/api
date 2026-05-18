"""Artifact generation configuration registry.

Maps artifact_type → ArtifactGenerateConfig, encapsulating per-artifact
metadata (valid resource types, entry types, draft requirements).

Used by the generation pipeline (prepare_generation) to validate
and configure generation requests per artifact type.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArtifactGenerateConfig:
    """Per-artifact configuration metadata for generation."""

    artifact_type: str
    valid_resource_types: list[str]
    prepare_sql_path: str
    draft_view_key: str
    requires_draft: bool = True
    has_artifact_id: bool = True
    fetcher_id_kwarg: str = ""
    entry_types: list[str] = field(default_factory=lambda: ["problems", "messages"])


REGISTRY: dict[str, ArtifactGenerateConfig] = {}


def _register(config: ArtifactGenerateConfig) -> None:
    REGISTRY[config.artifact_type] = config


# === Standard artifacts ===

_register(ArtifactGenerateConfig(
    artifact_type="persona",
    valid_resource_types=["names", "descriptions", "colors", "icons", "instructions", "flags", "examples", "parameter_fields", "departments", "voices"],
    prepare_sql_path="app/sql/queries/generate/persona/prepare_persona_generation_complete.sql",
    draft_view_key="draft_persona",
    requires_draft=False,
    fetcher_id_kwarg="persona_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="scenario",
    valid_resource_types=["names", "descriptions", "problem_statements", "objectives", "scenario_flags", "images", "videos", "questions", "departments", "parameter_fields", "personas", "documents"],
    prepare_sql_path="app/sql/queries/generate/scenario/prepare_scenario_generation_complete.sql",
    draft_view_key="draft_scenario",
    requires_draft=False,
    fetcher_id_kwarg="scenario_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="simulation",
    valid_resource_types=["names", "descriptions", "departments", "flags", "scenarios", "scenario_flags", "scenario_positions", "scenario_rubrics", "scenario_time_limits"],
    prepare_sql_path="app/sql/queries/generate/simulation/prepare_simulation_generation_complete.sql",
    draft_view_key="draft_simulation",
    requires_draft=False,
    fetcher_id_kwarg="simulation_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="cohort",
    valid_resource_types=["names", "descriptions", "flags", "departments", "simulations", "simulation_positions", "simulation_availability", "profiles", "profile_personas"],
    prepare_sql_path="app/sql/queries/generate/cohort/prepare_cohort_generation_complete.sql",
    draft_view_key="draft_cohort",
    requires_draft=False,
    fetcher_id_kwarg="cohort_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="agent",
    valid_resource_types=["names", "descriptions", "models", "prompts", "instructions", "flags", "departments", "tools", "temperature_levels", "reasoning_levels", "voices"],
    prepare_sql_path="app/sql/queries/generate/agent/prepare_agent_generation_complete.sql",
    draft_view_key="draft_agent",
    fetcher_id_kwarg="agent_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="auth",
    valid_resource_types=["names", "descriptions", "flags", "protocols", "slugs", "items"],
    prepare_sql_path="app/sql/queries/generate/auth/prepare_auth_generation_complete.sql",
    draft_view_key="draft_auth",
    fetcher_id_kwarg="auth_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="document",
    valid_resource_types=["names", "descriptions", "flags", "departments", "fields", "uploads", "images", "texts"],
    prepare_sql_path="app/sql/queries/generate/document/prepare_document_generation_complete.sql",
    draft_view_key="draft_document",
    requires_draft=False,
    fetcher_id_kwarg="document_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="rubric",
    valid_resource_types=["names", "descriptions", "departments", "flags", "points", "pass_points", "standard_groups", "standards"],
    prepare_sql_path="app/sql/queries/generate/rubric/prepare_rubric_generation_complete.sql",
    draft_view_key="draft_rubric",
    fetcher_id_kwarg="rubric_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="profile",
    valid_resource_types=["names", "flags", "request_limits", "departments", "emails", "cohorts"],
    prepare_sql_path="app/sql/queries/generate/profile/prepare_profile_generation_complete.sql",
    draft_view_key="draft_profile",
    fetcher_id_kwarg="target_profile_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="parameter",
    valid_resource_types=["names", "descriptions", "flags", "departments", "fields"],
    prepare_sql_path="app/sql/queries/generate/parameter/prepare_parameter_generation_complete.sql",
    draft_view_key="draft_parameter",
    fetcher_id_kwarg="parameter_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="field",
    valid_resource_types=["names", "descriptions", "flags", "departments", "conditional_parameters"],
    prepare_sql_path="app/sql/queries/generate/field/prepare_field_generation_complete.sql",
    draft_view_key="draft_field",
    fetcher_id_kwarg="field_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="model",
    valid_resource_types=["names", "descriptions", "values", "providers", "flags", "departments", "modalities", "temperature_levels", "pricing", "reasoning_levels", "qualities", "voices"],
    prepare_sql_path="app/sql/queries/generate/model/prepare_model_generation_complete.sql",
    draft_view_key="draft_model",
    fetcher_id_kwarg="model_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="tool",
    valid_resource_types=["names", "descriptions", "args", "arg_positions", "args_outputs", "flags"],
    prepare_sql_path="app/sql/queries/generate/tool/prepare_tool_generation_complete.sql",
    draft_view_key="draft_tool",
    fetcher_id_kwarg="tool_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="department",
    valid_resource_types=["names", "descriptions", "flags", "settings"],
    prepare_sql_path="app/sql/queries/generate/department/prepare_department_generation_complete.sql",
    draft_view_key="draft_department",
    fetcher_id_kwarg="department_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="provider",
    valid_resource_types=["names", "descriptions", "flags", "departments", "values", "endpoints"],
    prepare_sql_path="app/sql/queries/generate/provider/prepare_provider_generation_complete.sql",
    draft_view_key="draft_provider",
    fetcher_id_kwarg="provider_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="eval",
    valid_resource_types=["names", "descriptions", "flags", "departments", "agents", "run_positions", "group_positions", "run_rubrics", "group_rubrics", "rubrics"],
    prepare_sql_path="app/sql/queries/generate/eval/prepare_eval_generation_complete.sql",
    draft_view_key="draft_eval",
    fetcher_id_kwarg="eval_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="setting",
    valid_resource_types=["names", "descriptions", "colors", "flags", "departments", "profiles", "auths", "provider_keys", "auth_item_keys", "roles"],
    prepare_sql_path="app/sql/queries/generate/setting/prepare_setting_generation_complete.sql",
    draft_view_key="draft_setting",
    fetcher_id_kwarg="setting_id",
))

# === Pool-based artifacts ===

_register(ArtifactGenerateConfig(
    artifact_type="chat",
    valid_resource_types=["departments", "personas", "documents", "parameter_fields", "scenarios", "parameters", "fields", "questions", "options", "videos", "images", "templates", "problem_statements", "objectives"],
    prepare_sql_path="app/sql/queries/generate/training/prepare_training_generation_complete.sql",
    draft_view_key="draft_chat",
    fetcher_id_kwarg="chat_entry_id",
))

_register(ArtifactGenerateConfig(
    artifact_type="benchmark",
    valid_resource_types=["departments", "models", "prompts", "instructions", "voices", "temperature_levels", "reasoning_levels", "tools", "keys"],
    prepare_sql_path="app/sql/queries/generate/benchmark/prepare_benchmark_generation_complete.sql",
    draft_view_key="draft_invocation",
    has_artifact_id=False,
))

_register(ArtifactGenerateConfig(
    artifact_type="invocation",
    valid_resource_types=["departments", "models", "prompts", "instructions", "voices", "temperature_levels", "reasoning_levels", "tools", "keys"],
    prepare_sql_path="app/sql/queries/generate/suite/prepare_suite_generation_complete.sql",
    draft_view_key="draft_invocation",
    entry_types=[],
    requires_draft=False,
    fetcher_id_kwarg="benchmark_entry_id",
))

# === Attempt/test ===

_register(ArtifactGenerateConfig(
    artifact_type="attempt",
    valid_resource_types=[],  # Not used — operations-based dispatch
    prepare_sql_path="",  # Not used — prepare_generation handles context
    draft_view_key="",
    requires_draft=False,
    fetcher_id_kwarg="",
    entry_types=[],
))

_register(ArtifactGenerateConfig(
    artifact_type="test",
    valid_resource_types=["grades", "feedbacks"],
    prepare_sql_path="app/sql/queries/generate/persona/prepare_persona_generation_complete.sql",
    draft_view_key="draft_test",
    requires_draft=False,
    entry_types=["problems", "messages"],
    fetcher_id_kwarg="test_id",
))

# === Read-only / analytical artifacts ===

for _art in ["activity", "pricing", "reports", "leaderboard", "dashboard", "home", "practice"]:
    _register(ArtifactGenerateConfig(
        artifact_type=_art,
        valid_resource_types=["names", "descriptions", "flags", "departments"] if _art not in ("home", "practice") else [],
        prepare_sql_path=f"app/sql/queries/generate/{_art}/prepare_{_art}_generation_complete.sql",
        draft_view_key=f"draft_{_art}" if _art not in ("home", "practice") else "draft_training",
        entry_types=["problems", "messages"],
        requires_draft=False,
        has_artifact_id=False,
    ))
