"""Tool function registry — (operation, name) → (module_path, function_name).

Maps each tool target to the actual Python black-box function in the tools layer.
Used by the generation pipeline to resolve which function to pass to create_tool_call.

Allowed operations per layer:
  - Artifacts: create, update, delete, docs, search
  - Resources: create, refresh, search, docs
  - Entries:   create, refresh, search, docs
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

_T = "app.tools"


def resolve_tool_fn(
    layer: str,
    name: str,
    operation: str,
) -> Callable[..., Any] | None:
    """Look up (layer, name, operation) and return the imported callable.

    layer: "artifact", "resource", or "entry"
    name:  e.g. "names", "persona", "attempt_content"
    operation: e.g. "create", "search", "docs"

    Returns None if not registered.
    """
    registry = _REGISTRIES.get(layer)
    if not registry:
        return None
    entry = registry.get((operation, name))
    if entry is None:
        return None
    module_path, func_name = entry
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Artifacts — (operation, name) → (module_path, function_name)
# Operations: create, update, delete, docs, search
# ---------------------------------------------------------------------------

ARTIFACT_TOOL_FNS: dict[tuple[str, str], tuple[str, str]] = {
    # agent
    ("create", "agent"): (f"{_T}.artifacts.agent.create", "create_agent"),
    ("update", "agent"): (f"{_T}.artifacts.agent.update", "update_agent"),
    ("delete", "agent"): (f"{_T}.artifacts.agent.delete", "delete_agents"),
    ("docs", "agent"): (f"{_T}.artifacts.agent.docs", "get_agent_docs"),
    ("search", "agent"): (f"{_T}.artifacts.agent.search", "search_agents"),
    # auth
    ("create", "auth"): (f"{_T}.artifacts.auth.create", "create_auth"),
    ("update", "auth"): (f"{_T}.artifacts.auth.update", "update_auth"),
    ("delete", "auth"): (f"{_T}.artifacts.auth.delete", "delete_auths"),
    ("docs", "auth"): (f"{_T}.artifacts.auth.docs", "get_auth_docs"),
    ("search", "auth"): (f"{_T}.artifacts.auth.search", "search_auths"),
    # cohort
    ("create", "cohort"): (f"{_T}.artifacts.cohort.create", "create_cohort"),
    ("update", "cohort"): (f"{_T}.artifacts.cohort.update", "update_cohort"),
    ("delete", "cohort"): (f"{_T}.artifacts.cohort.delete", "delete_cohorts"),
    ("docs", "cohort"): (f"{_T}.artifacts.cohort.docs", "get_cohort_docs"),
    ("search", "cohort"): (f"{_T}.artifacts.cohort.search", "search_cohorts"),
    # department
    ("create", "department"): (
        f"{_T}.artifacts.department.create",
        "create_department",
    ),
    ("update", "department"): (
        f"{_T}.artifacts.department.update",
        "update_department",
    ),
    ("delete", "department"): (
        f"{_T}.artifacts.department.delete",
        "delete_departments",
    ),
    ("docs", "department"): (f"{_T}.artifacts.department.docs", "get_department_docs"),
    ("search", "department"): (
        f"{_T}.artifacts.department.search",
        "search_departments",
    ),
    # document
    ("create", "document"): (f"{_T}.artifacts.document.create", "create_document"),
    ("update", "document"): (f"{_T}.artifacts.document.update", "update_document"),
    ("delete", "document"): (f"{_T}.artifacts.document.delete", "delete_documents"),
    ("docs", "document"): (f"{_T}.artifacts.document.docs", "get_document_docs"),
    ("search", "document"): (f"{_T}.artifacts.document.search", "search_documents"),
    # eval
    ("create", "eval"): (f"{_T}.artifacts.eval.create", "create_eval"),
    ("update", "eval"): (f"{_T}.artifacts.eval.update", "update_eval"),
    ("delete", "eval"): (f"{_T}.artifacts.eval.delete", "delete_evals"),
    ("docs", "eval"): (f"{_T}.artifacts.eval.docs", "get_eval_docs"),
    ("search", "eval"): (f"{_T}.artifacts.eval.search", "search_evals"),
    # field
    ("create", "field"): (f"{_T}.artifacts.field.create", "create_field"),
    ("update", "field"): (f"{_T}.artifacts.field.update", "update_field"),
    ("delete", "field"): (f"{_T}.artifacts.field.delete", "delete_fields"),
    ("docs", "field"): (f"{_T}.artifacts.field.docs", "get_field_docs"),
    ("search", "field"): (f"{_T}.artifacts.field.search", "search_fields"),
    # model
    ("create", "model"): (f"{_T}.artifacts.model.create", "create_model"),
    ("update", "model"): (f"{_T}.artifacts.model.update", "update_model"),
    ("delete", "model"): (f"{_T}.artifacts.model.delete", "delete_models"),
    ("docs", "model"): (f"{_T}.artifacts.model.docs", "get_model_docs"),
    ("search", "model"): (f"{_T}.artifacts.model.search", "search_models"),
    # parameter
    ("create", "parameter"): (f"{_T}.artifacts.parameter.create", "create_parameter"),
    ("update", "parameter"): (f"{_T}.artifacts.parameter.update", "update_parameter"),
    ("delete", "parameter"): (f"{_T}.artifacts.parameter.delete", "delete_parameters"),
    ("docs", "parameter"): (f"{_T}.artifacts.parameter.docs", "get_parameter_docs"),
    ("search", "parameter"): (f"{_T}.artifacts.parameter.search", "search_parameters"),
    # persona
    ("create", "persona"): (f"{_T}.artifacts.persona.create", "create_persona"),
    ("update", "persona"): (f"{_T}.artifacts.persona.update", "update_persona"),
    ("delete", "persona"): (f"{_T}.artifacts.persona.delete", "delete_personas"),
    ("docs", "persona"): (f"{_T}.artifacts.persona.docs", "get_persona_docs"),
    ("search", "persona"): (f"{_T}.artifacts.persona.search", "search_personas"),
    # profile
    ("create", "profile"): (f"{_T}.artifacts.profile.create", "create_profile"),
    ("update", "profile"): (f"{_T}.artifacts.profile.update", "update_profile"),
    ("delete", "profile"): (f"{_T}.artifacts.profile.delete", "delete_profiles"),
    ("docs", "profile"): (f"{_T}.artifacts.profile.docs", "get_profile_docs"),
    ("search", "profile"): (f"{_T}.artifacts.profile.search", "search_profiles"),
    # provider
    ("create", "provider"): (f"{_T}.artifacts.provider.create", "create_provider"),
    ("update", "provider"): (f"{_T}.artifacts.provider.update", "update_provider"),
    ("delete", "provider"): (f"{_T}.artifacts.provider.delete", "delete_providers"),
    ("docs", "provider"): (f"{_T}.artifacts.provider.docs", "get_provider_docs"),
    ("search", "provider"): (f"{_T}.artifacts.provider.search", "search_providers"),
    # rubric
    ("create", "rubric"): (f"{_T}.artifacts.rubric.create", "create_rubric"),
    ("update", "rubric"): (f"{_T}.artifacts.rubric.update", "update_rubric"),
    ("delete", "rubric"): (f"{_T}.artifacts.rubric.delete", "delete_rubrics"),
    ("docs", "rubric"): (f"{_T}.artifacts.rubric.docs", "get_rubric_docs"),
    ("search", "rubric"): (f"{_T}.artifacts.rubric.search", "search_rubrics"),
    # scenario
    ("create", "scenario"): (f"{_T}.artifacts.scenario.create", "create_scenario"),
    ("update", "scenario"): (f"{_T}.artifacts.scenario.update", "update_scenario"),
    ("delete", "scenario"): (f"{_T}.artifacts.scenario.delete", "delete_scenarios"),
    ("docs", "scenario"): (f"{_T}.artifacts.scenario.docs", "get_scenario_docs"),
    ("search", "scenario"): (f"{_T}.artifacts.scenario.search", "search_scenarios"),
    # setting
    ("create", "setting"): (f"{_T}.artifacts.setting.create", "create_setting"),
    ("update", "setting"): (f"{_T}.artifacts.setting.update", "update_setting"),
    ("delete", "setting"): (f"{_T}.artifacts.setting.delete", "delete_settings"),
    ("docs", "setting"): (f"{_T}.artifacts.setting.docs", "get_setting_docs"),
    ("search", "setting"): (f"{_T}.artifacts.setting.search", "search_settings"),
    # simulation
    ("create", "simulation"): (
        f"{_T}.artifacts.simulation.create",
        "create_simulation",
    ),
    ("update", "simulation"): (
        f"{_T}.artifacts.simulation.update",
        "update_simulation",
    ),
    ("delete", "simulation"): (
        f"{_T}.artifacts.simulation.delete",
        "delete_simulations",
    ),
    ("docs", "simulation"): (f"{_T}.artifacts.simulation.docs", "get_simulation_docs"),
    ("search", "simulation"): (
        f"{_T}.artifacts.simulation.search",
        "search_simulations",
    ),
    # tool
    ("create", "tool"): (f"{_T}.artifacts.tool.create", "create_tool"),
    ("update", "tool"): (f"{_T}.artifacts.tool.update", "update_tool"),
    ("delete", "tool"): (f"{_T}.artifacts.tool.delete", "delete_tools"),
    ("docs", "tool"): (f"{_T}.artifacts.tool.docs", "get_tool_docs"),
    ("search", "tool"): (f"{_T}.artifacts.tool.search", "search_tools"),
}

# ---------------------------------------------------------------------------
# Resources — (operation, name) → (module_path, function_name)
# Operations: create, search, docs
# (refresh not implemented at resource level — resources are immutable)
# ---------------------------------------------------------------------------

RESOURCE_TOOL_FNS: dict[tuple[str, str], tuple[str, str]] = {
    # create
    ("create", "agents"): (f"{_T}.resources.agents.create", "create_agent"),
    ("create", "arg_positions"): (
        f"{_T}.resources.arg_positions.create",
        "create_arg_position",
    ),
    ("create", "args"): (f"{_T}.resources.args.create", "create_arg"),
    ("create", "args_outputs"): (
        f"{_T}.resources.args_outputs.create",
        "create_args_output",
    ),
    ("create", "artifacts"): (f"{_T}.resources.artifacts.create", "create_artifact"),
    ("create", "auth_item_keys"): (
        f"{_T}.resources.auth_item_keys.create",
        "create_auth_item_key",
    ),
    ("create", "auths"): (f"{_T}.resources.auths.create", "create_auth"),
    ("create", "cohorts"): (f"{_T}.resources.cohorts.create", "create_cohort"),
    ("create", "colors"): (f"{_T}.resources.colors.create", "create_color"),
    ("create", "conditional_parameters"): (
        f"{_T}.resources.conditional_parameters.create",
        "create_conditional_parameter",
    ),
    ("create", "departments"): (
        f"{_T}.resources.departments.create",
        "create_department",
    ),
    ("create", "descriptions"): (
        f"{_T}.resources.descriptions.create",
        "create_description",
    ),
    ("create", "documents"): (f"{_T}.resources.documents.create", "create_document"),
    ("create", "emails"): (f"{_T}.resources.emails.create", "create_email"),
    ("create", "endpoints"): (f"{_T}.resources.endpoints.create", "create_endpoint"),
    ("create", "entries"): (f"{_T}.resources.entries.create", "create_entry"),
    ("create", "evals"): (f"{_T}.resources.evals.create", "create_eval"),
    ("create", "examples"): (f"{_T}.resources.examples.create", "create_example"),
    ("create", "fields"): (f"{_T}.resources.fields.create", "create_field"),
    ("create", "files"): (f"{_T}.resources.files.create", "create_file"),
    ("create", "flags"): (f"{_T}.resources.flags.create", "create_flag"),
    ("create", "icons"): (f"{_T}.resources.icons.create", "create_icon"),
    ("create", "images"): (f"{_T}.resources.images.create", "create_image"),
    ("create", "instructions"): (
        f"{_T}.resources.instructions.create",
        "create_instruction",
    ),
    ("create", "items"): (f"{_T}.resources.items.create", "create_item"),
    ("create", "keys"): (f"{_T}.resources.keys.create", "create_key"),
    ("create", "modalities"): (f"{_T}.resources.modalities.create", "create_modality"),
    ("create", "model_flags"): (
        f"{_T}.resources.model_flags.create",
        "create_model_flag",
    ),
    ("create", "model_positions"): (
        f"{_T}.resources.model_positions.create",
        "create_model_position",
    ),
    ("create", "model_rubrics"): (
        f"{_T}.resources.model_rubrics.create",
        "create_model_rubric",
    ),
    ("create", "models"): (f"{_T}.resources.models.create", "create_model"),
    ("create", "names"): (f"{_T}.resources.names.create", "create_name"),
    ("create", "objectives"): (f"{_T}.resources.objectives.create", "create_objective"),
    ("create", "operations"): (f"{_T}.resources.operations.create", "create_operation"),
    ("create", "options"): (f"{_T}.resources.options.create", "create_option"),
    ("create", "parameter_fields"): (
        f"{_T}.resources.parameter_fields.create",
        "create_parameter_field",
    ),
    ("create", "parameters"): (f"{_T}.resources.parameters.create", "create_parameter"),
    ("create", "personas"): (f"{_T}.resources.personas.create", "create_persona"),
    ("create", "points"): (f"{_T}.resources.points.create", "create_point"),
    ("create", "pricing"): (f"{_T}.resources.pricing.create", "create_pricing"),
    ("create", "problem_statements"): (
        f"{_T}.resources.problem_statements.create",
        "create_problem_statement",
    ),
    ("create", "profile_personas"): (
        f"{_T}.resources.profile_personas.create",
        "create_profile_persona",
    ),
    ("create", "profiles"): (f"{_T}.resources.profiles.create", "create_profile"),
    ("create", "prompts"): (f"{_T}.resources.prompts.create", "create_prompt"),
    ("create", "protocols"): (f"{_T}.resources.protocols.create", "create_protocol"),
    ("create", "provider_keys"): (
        f"{_T}.resources.provider_keys.create",
        "create_provider_key",
    ),
    ("create", "providers"): (f"{_T}.resources.providers.create", "create_provider"),
    ("create", "qualities"): (f"{_T}.resources.qualities.create", "create_quality"),
    ("create", "questions"): (f"{_T}.resources.questions.create", "create_question"),
    ("create", "reasoning_levels"): (
        f"{_T}.resources.reasoning_levels.create",
        "create_reasoning_level",
    ),
    ("create", "request_limits"): (
        f"{_T}.resources.request_limits.create",
        "create_request_limit",
    ),
    ("create", "resources"): (f"{_T}.resources.resources.create", "create_resource"),
    ("create", "roles"): (f"{_T}.resources.roles.create", "create_role"),
    ("create", "rubrics"): (f"{_T}.resources.rubrics.create", "create_rubric"),
    ("create", "scenario_flags"): (
        f"{_T}.resources.scenario_flags.create",
        "create_scenario_flag",
    ),
    ("create", "scenario_positions"): (
        f"{_T}.resources.scenario_positions.create",
        "create_scenario_position",
    ),
    ("create", "scenario_rubrics"): (
        f"{_T}.resources.scenario_rubrics.create",
        "create_scenario_rubric",
    ),
    ("create", "scenario_time_limits"): (
        f"{_T}.resources.scenario_time_limits.create",
        "create_scenario_time_limit",
    ),
    ("create", "scenarios"): (f"{_T}.resources.scenarios.create", "create_scenario"),
    ("create", "settings"): (f"{_T}.resources.settings.create", "create_setting"),
    ("create", "simulation_availability"): (
        f"{_T}.resources.simulation_availability.create",
        "create_simulation_availability",
    ),
    ("create", "simulation_positions"): (
        f"{_T}.resources.simulation_positions.create",
        "create_simulation_position",
    ),
    ("create", "simulations"): (
        f"{_T}.resources.simulations.create",
        "create_simulation",
    ),
    ("create", "slugs"): (f"{_T}.resources.slugs.create", "create_slug"),
    ("create", "standard_groups"): (
        f"{_T}.resources.standard_groups.create",
        "create_standard_group",
    ),
    ("create", "standards"): (f"{_T}.resources.standards.create", "create_standard"),
    ("create", "systems"): (f"{_T}.resources.systems.create", "create_system"),
    ("create", "temperature_levels"): (
        f"{_T}.resources.temperature_levels.create",
        "create_temperature_level",
    ),
    ("create", "texts"): (f"{_T}.resources.texts.create", "create_text"),
    ("create", "thresholds"): (f"{_T}.resources.thresholds.create", "create_threshold"),
    ("create", "tools"): (f"{_T}.resources.tools.create", "create_tool"),
    ("create", "values"): (f"{_T}.resources.values.create", "create_value"),
    ("create", "videos"): (f"{_T}.resources.videos.create", "create_video"),
    ("create", "voices"): (f"{_T}.resources.voices.create", "create_voice"),
    # search
    ("search", "agents"): (f"{_T}.resources.agents.search", "search_agents"),
    ("search", "arg_positions"): (
        f"{_T}.resources.arg_positions.search",
        "search_arg_positions",
    ),
    ("search", "args"): (f"{_T}.resources.args.search", "search_args"),
    ("search", "args_outputs"): (
        f"{_T}.resources.args_outputs.search",
        "search_args_outputs",
    ),
    ("search", "artifacts"): (f"{_T}.resources.artifacts.search", "search_artifacts"),
    ("search", "auth_item_keys"): (
        f"{_T}.resources.auth_item_keys.search",
        "search_auth_item_keys",
    ),
    ("search", "auths"): (f"{_T}.resources.auths.search", "search_auths"),
    ("search", "cohorts"): (f"{_T}.resources.cohorts.search", "search_cohorts"),
    ("search", "colors"): (f"{_T}.resources.colors.search", "search_colors"),
    ("search", "conditional_parameters"): (
        f"{_T}.resources.conditional_parameters.search",
        "search_conditional_parameters",
    ),
    ("search", "departments"): (
        f"{_T}.resources.departments.search",
        "search_departments",
    ),
    ("search", "descriptions"): (
        f"{_T}.resources.descriptions.search",
        "search_descriptions",
    ),
    ("search", "documents"): (f"{_T}.resources.documents.search", "search_documents"),
    ("search", "emails"): (f"{_T}.resources.emails.search", "search_emails"),
    ("search", "endpoints"): (f"{_T}.resources.endpoints.search", "search_endpoints"),
    ("search", "entries"): (f"{_T}.resources.entries.search", "search_entries"),
    ("search", "evals"): (f"{_T}.resources.evals.search", "search_evals"),
    ("search", "examples"): (f"{_T}.resources.examples.search", "search_examples"),
    ("search", "fields"): (f"{_T}.resources.fields.search", "search_fields"),
    ("search", "files"): (f"{_T}.resources.files.search", "search_files"),
    ("search", "flags"): (f"{_T}.resources.flags.search", "search_flags"),
    ("search", "icons"): (f"{_T}.resources.icons.search", "search_icons"),
    ("search", "images"): (f"{_T}.resources.images.search", "search_images"),
    ("search", "instructions"): (
        f"{_T}.resources.instructions.search",
        "search_instructions",
    ),
    ("search", "items"): (f"{_T}.resources.items.search", "search_items"),
    ("search", "keys"): (f"{_T}.resources.keys.search", "search_keys"),
    ("search", "modalities"): (
        f"{_T}.resources.modalities.search",
        "search_modalities",
    ),
    ("search", "model_flags"): (
        f"{_T}.resources.model_flags.search",
        "search_model_flags",
    ),
    ("search", "model_positions"): (
        f"{_T}.resources.model_positions.search",
        "search_model_positions",
    ),
    ("search", "model_rubrics"): (
        f"{_T}.resources.model_rubrics.search",
        "search_model_rubrics",
    ),
    ("search", "models"): (f"{_T}.resources.models.search", "search_models"),
    ("search", "names"): (f"{_T}.resources.names.search", "search_names"),
    ("search", "objectives"): (
        f"{_T}.resources.objectives.search",
        "search_objectives",
    ),
    ("search", "operations"): (
        f"{_T}.resources.operations.search",
        "search_operations",
    ),
    ("search", "options"): (f"{_T}.resources.options.search", "search_options"),
    ("search", "parameter_fields"): (
        f"{_T}.resources.parameter_fields.search",
        "search_parameter_fields",
    ),
    ("search", "parameters"): (
        f"{_T}.resources.parameters.search",
        "search_parameters",
    ),
    ("search", "personas"): (f"{_T}.resources.personas.search", "search_personas"),
    ("search", "points"): (f"{_T}.resources.points.search", "search_points"),
    ("search", "pricing"): (f"{_T}.resources.pricing.search", "search_pricing"),
    ("search", "problem_statements"): (
        f"{_T}.resources.problem_statements.search",
        "search_problem_statements",
    ),
    ("search", "profile_personas"): (
        f"{_T}.resources.profile_personas.search",
        "search_profile_personas",
    ),
    ("search", "profiles"): (f"{_T}.resources.profiles.search", "search_profiles"),
    ("search", "prompts"): (f"{_T}.resources.prompts.search", "search_prompts"),
    ("search", "protocols"): (f"{_T}.resources.protocols.search", "search_protocols"),
    ("search", "provider_keys"): (
        f"{_T}.resources.provider_keys.search",
        "search_provider_keys",
    ),
    ("search", "providers"): (f"{_T}.resources.providers.search", "search_providers"),
    ("search", "qualities"): (f"{_T}.resources.qualities.search", "search_qualities"),
    ("search", "questions"): (f"{_T}.resources.questions.search", "search_questions"),
    ("search", "reasoning_levels"): (
        f"{_T}.resources.reasoning_levels.search",
        "search_reasoning_levels",
    ),
    ("search", "request_limits"): (
        f"{_T}.resources.request_limits.search",
        "search_request_limits",
    ),
    ("search", "resources"): (f"{_T}.resources.resources.search", "search_resources"),
    ("search", "roles"): (f"{_T}.resources.roles.search", "search_roles"),
    ("search", "rubrics"): (f"{_T}.resources.rubrics.search", "search_rubrics"),
    ("search", "scenario_flags"): (
        f"{_T}.resources.scenario_flags.search",
        "search_scenario_flags",
    ),
    ("search", "scenario_positions"): (
        f"{_T}.resources.scenario_positions.search",
        "search_scenario_positions",
    ),
    ("search", "scenario_rubrics"): (
        f"{_T}.resources.scenario_rubrics.search",
        "search_scenario_rubrics",
    ),
    ("search", "scenario_time_limits"): (
        f"{_T}.resources.scenario_time_limits.search",
        "search_scenario_time_limits",
    ),
    ("search", "scenarios"): (f"{_T}.resources.scenarios.search", "search_scenarios"),
    ("search", "settings"): (f"{_T}.resources.settings.search", "search_settings"),
    ("search", "simulation_availability"): (
        f"{_T}.resources.simulation_availability.search",
        "search_simulation_availability",
    ),
    ("search", "simulation_positions"): (
        f"{_T}.resources.simulation_positions.search",
        "search_simulation_positions",
    ),
    ("search", "simulations"): (
        f"{_T}.resources.simulations.search",
        "search_simulations",
    ),
    ("search", "slugs"): (f"{_T}.resources.slugs.search", "search_slugs"),
    ("search", "standard_groups"): (
        f"{_T}.resources.standard_groups.search",
        "search_standard_groups",
    ),
    ("search", "standards"): (f"{_T}.resources.standards.search", "search_standards"),
    ("search", "systems"): (f"{_T}.resources.systems.search", "search_systems"),
    ("search", "temperature_levels"): (
        f"{_T}.resources.temperature_levels.search",
        "_search_temperature_level_ids",
    ),
    ("search", "texts"): (f"{_T}.resources.texts.search", "search_texts"),
    ("search", "thresholds"): (
        f"{_T}.resources.thresholds.search",
        "search_thresholds",
    ),
    ("search", "tools"): (f"{_T}.resources.tools.search", "search_tools"),
    ("search", "values"): (f"{_T}.resources.values.search", "search_values"),
    ("search", "videos"): (f"{_T}.resources.videos.search", "search_videos"),
    ("search", "voices"): (f"{_T}.resources.voices.search", "search_voices"),
    # docs
    ("docs", "agents"): (f"{_T}.resources.agents.docs", "get_agents_docs"),
    ("docs", "arg_positions"): (
        f"{_T}.resources.arg_positions.docs",
        "get_arg_positions_docs",
    ),
    ("docs", "args"): (f"{_T}.resources.args.docs", "get_args_docs"),
    ("docs", "args_outputs"): (
        f"{_T}.resources.args_outputs.docs",
        "get_args_outputs_docs",
    ),
    ("docs", "artifacts"): (f"{_T}.resources.artifacts.docs", "get_artifacts_docs"),
    ("docs", "auth_item_keys"): (
        f"{_T}.resources.auth_item_keys.docs",
        "get_auth_item_keys_docs",
    ),
    ("docs", "auths"): (f"{_T}.resources.auths.docs", "get_auths_docs"),
    ("docs", "cohorts"): (f"{_T}.resources.cohorts.docs", "get_cohorts_docs"),
    ("docs", "colors"): (f"{_T}.resources.colors.docs", "get_colors_docs"),
    ("docs", "conditional_parameters"): (
        f"{_T}.resources.conditional_parameters.docs",
        "get_conditional_parameters_docs",
    ),
    ("docs", "departments"): (
        f"{_T}.resources.departments.docs",
        "get_departments_docs",
    ),
    ("docs", "descriptions"): (
        f"{_T}.resources.descriptions.docs",
        "get_descriptions_docs",
    ),
    ("docs", "documents"): (f"{_T}.resources.documents.docs", "get_documents_docs"),
    ("docs", "emails"): (f"{_T}.resources.emails.docs", "get_emails_docs"),
    ("docs", "endpoints"): (f"{_T}.resources.endpoints.docs", "get_endpoints_docs"),
    ("docs", "entries"): (f"{_T}.resources.entries.docs", "get_entries_docs"),
    ("docs", "evals"): (f"{_T}.resources.evals.docs", "get_evals_docs"),
    ("docs", "examples"): (f"{_T}.resources.examples.docs", "get_examples_docs"),
    ("docs", "fields"): (f"{_T}.resources.fields.docs", "get_fields_docs"),
    ("docs", "files"): (f"{_T}.resources.files.docs", "get_files_docs"),
    ("docs", "flags"): (f"{_T}.resources.flags.docs", "get_flags_docs"),
    ("docs", "icons"): (f"{_T}.resources.icons.docs", "get_icons_docs"),
    ("docs", "images"): (f"{_T}.resources.images.docs", "get_images_docs"),
    ("docs", "instructions"): (
        f"{_T}.resources.instructions.docs",
        "get_instructions_docs",
    ),
    ("docs", "items"): (f"{_T}.resources.items.docs", "get_items_docs"),
    ("docs", "keys"): (f"{_T}.resources.keys.docs", "get_keys_docs"),
    ("docs", "modalities"): (f"{_T}.resources.modalities.docs", "get_modalities_docs"),
    ("docs", "model_flags"): (
        f"{_T}.resources.model_flags.docs",
        "get_model_flags_docs",
    ),
    ("docs", "model_positions"): (
        f"{_T}.resources.model_positions.docs",
        "get_model_positions_docs",
    ),
    ("docs", "model_rubrics"): (
        f"{_T}.resources.model_rubrics.docs",
        "get_model_rubrics_docs",
    ),
    ("docs", "models"): (f"{_T}.resources.models.docs", "get_models_docs"),
    ("docs", "names"): (f"{_T}.resources.names.docs", "get_names_docs"),
    ("docs", "objectives"): (f"{_T}.resources.objectives.docs", "get_objectives_docs"),
    ("docs", "operations"): (f"{_T}.resources.operations.docs", "get_operations_docs"),
    ("docs", "options"): (f"{_T}.resources.options.docs", "get_options_docs"),
    ("docs", "parameter_fields"): (
        f"{_T}.resources.parameter_fields.docs",
        "get_parameter_fields_docs",
    ),
    ("docs", "parameters"): (f"{_T}.resources.parameters.docs", "get_parameters_docs"),
    ("docs", "personas"): (f"{_T}.resources.personas.docs", "get_personas_docs"),
    ("docs", "points"): (f"{_T}.resources.points.docs", "get_points_docs"),
    ("docs", "pricing"): (f"{_T}.resources.pricing.docs", "get_pricing_docs"),
    ("docs", "problem_statements"): (
        f"{_T}.resources.problem_statements.docs",
        "get_problem_statements_docs",
    ),
    ("docs", "profile_personas"): (
        f"{_T}.resources.profile_personas.docs",
        "get_profile_personas_docs",
    ),
    ("docs", "profiles"): (f"{_T}.resources.profiles.docs", "get_profiles_docs"),
    ("docs", "prompts"): (f"{_T}.resources.prompts.docs", "get_prompts_docs"),
    ("docs", "protocols"): (f"{_T}.resources.protocols.docs", "get_protocols_docs"),
    ("docs", "provider_keys"): (
        f"{_T}.resources.provider_keys.docs",
        "get_provider_keys_docs",
    ),
    ("docs", "providers"): (f"{_T}.resources.providers.docs", "get_providers_docs"),
    ("docs", "qualities"): (f"{_T}.resources.qualities.docs", "get_qualities_docs"),
    ("docs", "questions"): (f"{_T}.resources.questions.docs", "get_questions_docs"),
    ("docs", "reasoning_levels"): (
        f"{_T}.resources.reasoning_levels.docs",
        "get_reasoning_levels_docs",
    ),
    ("docs", "request_limits"): (
        f"{_T}.resources.request_limits.docs",
        "get_request_limits_docs",
    ),
    ("docs", "resources"): (f"{_T}.resources.resources.docs", "get_resources_docs"),
    ("docs", "roles"): (f"{_T}.resources.roles.docs", "get_roles_docs"),
    ("docs", "rubrics"): (f"{_T}.resources.rubrics.docs", "get_rubrics_docs"),
    ("docs", "scenario_flags"): (
        f"{_T}.resources.scenario_flags.docs",
        "get_scenario_flags_docs",
    ),
    ("docs", "scenario_positions"): (
        f"{_T}.resources.scenario_positions.docs",
        "get_scenario_positions_docs",
    ),
    ("docs", "scenario_rubrics"): (
        f"{_T}.resources.scenario_rubrics.docs",
        "get_scenario_rubrics_docs",
    ),
    ("docs", "scenario_time_limits"): (
        f"{_T}.resources.scenario_time_limits.docs",
        "get_scenario_time_limits_docs",
    ),
    ("docs", "scenarios"): (f"{_T}.resources.scenarios.docs", "get_scenarios_docs"),
    ("docs", "settings"): (f"{_T}.resources.settings.docs", "get_settings_docs"),
    ("docs", "simulation_availability"): (
        f"{_T}.resources.simulation_availability.docs",
        "get_simulation_availability_docs",
    ),
    ("docs", "simulation_positions"): (
        f"{_T}.resources.simulation_positions.docs",
        "get_simulation_positions_docs",
    ),
    ("docs", "simulations"): (
        f"{_T}.resources.simulations.docs",
        "get_simulations_docs",
    ),
    ("docs", "slugs"): (f"{_T}.resources.slugs.docs", "get_slugs_docs"),
    ("docs", "standard_groups"): (
        f"{_T}.resources.standard_groups.docs",
        "get_standard_groups_docs",
    ),
    ("docs", "standards"): (f"{_T}.resources.standards.docs", "get_standards_docs"),
    ("docs", "systems"): (f"{_T}.resources.systems.docs", "get_systems_docs"),
    ("docs", "temperature_levels"): (
        f"{_T}.resources.temperature_levels.docs",
        "get_temperature_levels_docs",
    ),
    ("docs", "texts"): (f"{_T}.resources.texts.docs", "get_texts_docs"),
    ("docs", "thresholds"): (f"{_T}.resources.thresholds.docs", "get_thresholds_docs"),
    ("docs", "tools"): (f"{_T}.resources.tools.docs", "get_tools_docs"),
    ("docs", "values"): (f"{_T}.resources.values.docs", "get_values_docs"),
    ("docs", "videos"): (f"{_T}.resources.videos.docs", "get_videos_docs"),
    ("docs", "voices"): (f"{_T}.resources.voices.docs", "get_voices_docs"),
}

# ---------------------------------------------------------------------------
# Entries — (operation, name) → (module_path, function_name)
# Operations: create, refresh, search, docs
# ---------------------------------------------------------------------------

ENTRY_TOOL_FNS: dict[tuple[str, str], tuple[str, str]] = {
    # create
    ("create", "activity"): (f"{_T}.entries.activity.create", "create_activity"),
    ("create", "agent_drafts"): (
        f"{_T}.entries.agent_drafts.create",
        "create_agent_draft",
    ),
    ("create", "attempt"): (f"{_T}.entries.attempt.create", "create_attempt"),
    ("create", "attempt_analysis"): (
        f"{_T}.entries.attempt_analysis.create",
        "create_attempt_analysis",
    ),
    ("create", "attempt_archive"): (
        f"{_T}.entries.attempt_archive.create",
        "create_attempt_archive",
    ),
    ("create", "attempt_chat"): (
        f"{_T}.entries.attempt_chat.create",
        "create_attempt_chat",
    ),
    ("create", "attempt_chat_bridge"): (
        f"{_T}.entries.attempt_chat_bridge.create",
        "create_attempt_chat_bridge",
    ),
    ("create", "attempt_chat_completion"): (
        f"{_T}.entries.attempt_chat_completion.create",
        "create_attempt_chat_completion",
    ),
    ("create", "attempt_content"): (
        f"{_T}.entries.attempt_content.create",
        "create_attempt_content",
    ),
    ("create", "attempt_conversation_completion"): (
        f"{_T}.entries.attempt_conversation_completion.create",
        "create_attempt_conversation_completion",
    ),
    ("create", "attempt_conversations"): (
        f"{_T}.entries.attempt_conversations.create",
        "create_attempt_conversations",
    ),
    ("create", "attempt_feedback"): (
        f"{_T}.entries.attempt_feedback.create",
        "create_attempt_feedback",
    ),
    ("create", "attempt_grade"): (
        f"{_T}.entries.attempt_grade.create",
        "create_attempt_grade",
    ),
    ("create", "attempt_highlight"): (
        f"{_T}.entries.attempt_highlight.create",
        "create_attempt_highlight",
    ),
    ("create", "attempt_hint"): (
        f"{_T}.entries.attempt_hint.create",
        "create_attempt_hint",
    ),
    ("create", "attempt_home"): (
        f"{_T}.entries.attempt_home.create",
        "create_attempt_home",
    ),
    ("create", "attempt_improvement"): (
        f"{_T}.entries.attempt_improvement.create",
        "create_attempt_improvement",
    ),
    ("create", "attempt_message"): (
        f"{_T}.entries.attempt_message.create",
        "create_attempt_message",
    ),
    ("create", "attempt_message_tree"): (
        f"{_T}.entries.attempt_message_tree.create",
        "create_attempt_message_tree",
    ),
    ("create", "attempt_mutes"): (
        f"{_T}.entries.attempt_mutes.create",
        "create_attempt_mutes",
    ),
    ("create", "attempt_practice"): (
        f"{_T}.entries.attempt_practice.create",
        "create_attempt_practice",
    ),
    ("create", "attempt_replacement"): (
        f"{_T}.entries.attempt_replacement.create",
        "create_attempt_replacement",
    ),
    ("create", "attempt_responses"): (
        f"{_T}.entries.attempt_responses.create",
        "create_attempt_responses",
    ),
    ("create", "attempt_strength"): (
        f"{_T}.entries.attempt_strength.create",
        "create_attempt_strength",
    ),
    ("create", "audio_uploads"): (
        f"{_T}.entries.audio_uploads.create",
        "create_audio_upload",
    ),
    ("create", "audios"): (f"{_T}.entries.audios.create", "create_audio"),
    ("create", "auth_drafts"): (
        f"{_T}.entries.auth_drafts.create",
        "create_auth_draft",
    ),
    ("create", "benchmark"): (f"{_T}.entries.benchmark.create", "create_benchmark"),
    ("create", "benchmark_test"): (
        f"{_T}.entries.benchmark_test.create",
        "create_benchmark_test",
    ),
    ("create", "call_uploads"): (
        f"{_T}.entries.call_uploads.create",
        "create_call_upload",
    ),
    ("create", "calls"): (f"{_T}.entries.calls.create", "create_call"),
    ("create", "chat"): (f"{_T}.entries.chat.create", "create_chat"),
    ("create", "chat_drafts"): (
        f"{_T}.entries.chat_drafts.create",
        "create_chat_draft",
    ),
    ("create", "cohort_drafts"): (
        f"{_T}.entries.cohort_drafts.create",
        "create_cohort_draft",
    ),
    ("create", "department_drafts"): (
        f"{_T}.entries.department_drafts.create",
        "create_department_draft",
    ),
    ("create", "document_drafts"): (
        f"{_T}.entries.document_drafts.create",
        "create_document_draft",
    ),
    ("create", "emulations"): (f"{_T}.entries.emulations.create", "create_emulation"),
    ("create", "eval_drafts"): (
        f"{_T}.entries.eval_drafts.create",
        "create_eval_draft",
    ),
    ("create", "field_drafts"): (
        f"{_T}.entries.field_drafts.create",
        "create_field_draft",
    ),
    ("create", "file_uploads"): (
        f"{_T}.entries.file_uploads.create",
        "create_file_upload",
    ),
    ("create", "files"): (f"{_T}.entries.files.create", "create_file"),
    ("create", "grant_consumptions"): (
        f"{_T}.entries.grant_consumptions.create",
        "create_grant_consumption",
    ),
    ("create", "grants"): (f"{_T}.entries.grants.create", "create_grant"),
    ("create", "groups"): (f"{_T}.entries.groups.create", "create_group"),
    ("create", "health"): (f"{_T}.entries.health.create", "create_health"),
    ("create", "home"): (f"{_T}.entries.home.create", "create_home"),
    ("create", "home_chat"): (f"{_T}.entries.home_chat.create", "create_home_chat"),
    ("create", "image_uploads"): (
        f"{_T}.entries.image_uploads.create",
        "create_image_upload",
    ),
    ("create", "images"): (f"{_T}.entries.images.create", "create_image"),
    ("create", "invocation"): (f"{_T}.entries.invocation.create", "create_invocation"),
    ("create", "invocation_drafts"): (
        f"{_T}.entries.invocation_drafts.create",
        "create_invocation_draft",
    ),
    ("create", "logins"): (f"{_T}.entries.logins.create", "create_login"),
    ("create", "message_uploads"): (
        f"{_T}.entries.message_uploads.create",
        "create_message_upload",
    ),
    ("create", "messages"): (f"{_T}.entries.messages.create", "create_message"),
    ("create", "attempt_message_completion"): (
        f"{_T}.entries.attempt_message_completion.create",
        "create_attempt_message_completion",
    ),
    ("create", "metrics"): (
        f"{_T}.entries.metrics.create",
        "create_metrics_entry_internal",
    ),
    ("create", "model_drafts"): (
        f"{_T}.entries.model_drafts.create",
        "create_model_draft",
    ),
    ("create", "parameter_drafts"): (
        f"{_T}.entries.parameter_drafts.create",
        "create_parameter_draft",
    ),
    ("create", "persona"): (f"{_T}.entries.persona.create", "create_persona"),
    ("create", "persona_drafts"): (
        f"{_T}.entries.persona_drafts.create",
        "create_persona_draft",
    ),
    ("create", "personas"): (f"{_T}.entries.personas.create", "create_personas"),
    ("create", "practice"): (f"{_T}.entries.practice.create", "create_practice"),
    ("create", "practice_chat"): (
        f"{_T}.entries.practice_chat.create",
        "create_practice_chat",
    ),
    ("create", "problems"): (f"{_T}.entries.problems.create", "create_problem"),
    ("create", "profile_drafts"): (
        f"{_T}.entries.profile_drafts.create",
        "create_profile_draft",
    ),
    ("create", "provider_drafts"): (
        f"{_T}.entries.provider_drafts.create",
        "create_provider_draft",
    ),
    ("create", "resolves"): (f"{_T}.entries.resolves.create", "create_resolve"),
    ("create", "rubric_drafts"): (
        f"{_T}.entries.rubric_drafts.create",
        "create_rubric_draft",
    ),
    ("create", "run_pricing"): (
        f"{_T}.entries.run_pricing.create",
        "create_run_pricing_entry_internal",
    ),
    ("create", "runs"): (f"{_T}.entries.runs.create", "create_run"),
    ("create", "scenario_drafts"): (
        f"{_T}.entries.scenario_drafts.create",
        "create_scenario_draft",
    ),
    ("create", "sessions"): (f"{_T}.entries.sessions.create", "create_session"),
    ("create", "setting_drafts"): (
        f"{_T}.entries.setting_drafts.create",
        "create_setting_draft",
    ),
    ("create", "simulation_drafts"): (
        f"{_T}.entries.simulation_drafts.create",
        "create_simulation_draft",
    ),
    ("create", "test"): (f"{_T}.entries.test.create", "create_test"),
    ("create", "test_archive"): (
        f"{_T}.entries.test_archive.create",
        "create_test_archive",
    ),
    ("create", "test_invocation_completion"): (
        f"{_T}.entries.test_invocation_completion.create",
        "create_test_invocation_completion",
    ),
    ("create", "test_feedback"): (
        f"{_T}.entries.test_feedback.create",
        "create_test_feedback",
    ),
    ("create", "test_grade"): (f"{_T}.entries.test_grade.create", "create_test_grade"),
    ("create", "test_invocation"): (
        f"{_T}.entries.test_invocation.create",
        "create_test_invocation",
    ),
    ("create", "test_invocation_bridge"): (
        f"{_T}.entries.test_invocation_bridge.create",
        "create_test_invocation_bridge",
    ),
    ("create", "test_invocation_groups"): (
        f"{_T}.entries.test_invocation_groups.create",
        "create_test_invocation_groups",
    ),
    ("create", "test_invocation_runs"): (
        f"{_T}.entries.test_invocation_runs.create",
        "create_test_invocation_runs",
    ),
    ("create", "text_uploads"): (
        f"{_T}.entries.text_uploads.create",
        "create_text_upload",
    ),
    ("create", "texts"): (f"{_T}.entries.texts.create", "create_text"),
    ("create", "tokens"): (f"{_T}.entries.tokens.create", "create_token"),
    ("create", "tool_drafts"): (
        f"{_T}.entries.tool_drafts.create",
        "create_tool_draft",
    ),
    ("create", "uploads"): (f"{_T}.entries.uploads.create", "create_upload"),
    ("create", "upload_completion"): (
        f"{_T}.entries.upload_completion.create",
        "create_upload_completion",
    ),
    ("create", "video_uploads"): (
        f"{_T}.entries.video_uploads.create",
        "create_video_upload",
    ),
    ("create", "videos"): (f"{_T}.entries.videos.create", "create_video"),
    # refresh (entries only)
    ("refresh", "activity"): (f"{_T}.entries.activity.refresh", "refresh_activity"),
    ("refresh", "agent_drafts"): (
        f"{_T}.entries.agent_drafts.refresh",
        "refresh_agent_drafts",
    ),
    ("refresh", "attempt"): (f"{_T}.entries.attempt.refresh", "refresh_attempt"),
    ("refresh", "attempt_analysis"): (
        f"{_T}.entries.attempt_analysis.refresh",
        "refresh_attempt_analysis",
    ),
    ("refresh", "attempt_archive"): (
        f"{_T}.entries.attempt_archive.refresh",
        "refresh_attempt_archive",
    ),
    ("refresh", "attempt_chat"): (
        f"{_T}.entries.attempt_chat.refresh",
        "refresh_attempt_chat",
    ),
    ("refresh", "attempt_chat_bridge"): (
        f"{_T}.entries.attempt_chat_bridge.refresh",
        "refresh_attempt_chat_bridge",
    ),
    ("refresh", "attempt_chat_completion"): (
        f"{_T}.entries.attempt_chat_completion.refresh",
        "refresh_attempt_chat_completion",
    ),
    ("refresh", "attempt_content"): (
        f"{_T}.entries.attempt_content.refresh",
        "refresh_attempt_content",
    ),
    ("refresh", "attempt_conversation_completion"): (
        f"{_T}.entries.attempt_conversation_completion.refresh",
        "refresh_attempt_conversation_completion",
    ),
    ("refresh", "attempt_conversations"): (
        f"{_T}.entries.attempt_conversations.refresh",
        "refresh_attempt_conversations",
    ),
    ("refresh", "attempt_feedback"): (
        f"{_T}.entries.attempt_feedback.refresh",
        "refresh_attempt_feedback",
    ),
    ("refresh", "attempt_grade"): (
        f"{_T}.entries.attempt_grade.refresh",
        "refresh_attempt_grade",
    ),
    ("refresh", "attempt_highlight"): (
        f"{_T}.entries.attempt_highlight.refresh",
        "refresh_attempt_highlight",
    ),
    ("refresh", "attempt_hint"): (
        f"{_T}.entries.attempt_hint.refresh",
        "refresh_attempt_hint",
    ),
    ("refresh", "attempt_home"): (
        f"{_T}.entries.attempt_home.refresh",
        "refresh_attempt_home",
    ),
    ("refresh", "attempt_improvement"): (
        f"{_T}.entries.attempt_improvement.refresh",
        "refresh_attempt_improvement",
    ),
    ("refresh", "attempt_message"): (
        f"{_T}.entries.attempt_message.refresh",
        "refresh_attempt_message",
    ),
    ("refresh", "attempt_message_tree"): (
        f"{_T}.entries.attempt_message_tree.refresh",
        "refresh_attempt_message_tree",
    ),
    ("refresh", "attempt_mutes"): (
        f"{_T}.entries.attempt_mutes.refresh",
        "refresh_attempt_mutes",
    ),
    ("refresh", "attempt_practice"): (
        f"{_T}.entries.attempt_practice.refresh",
        "refresh_attempt_practice",
    ),
    ("refresh", "attempt_replacement"): (
        f"{_T}.entries.attempt_replacement.refresh",
        "refresh_attempt_replacement",
    ),
    ("refresh", "attempt_responses"): (
        f"{_T}.entries.attempt_responses.refresh",
        "refresh_attempt_responses",
    ),
    ("refresh", "attempt_strength"): (
        f"{_T}.entries.attempt_strength.refresh",
        "refresh_attempt_strength",
    ),
    ("refresh", "audio_uploads"): (
        f"{_T}.entries.audio_uploads.refresh",
        "refresh_audio_uploads",
    ),
    ("refresh", "audios"): (f"{_T}.entries.audios.refresh", "refresh_audios_internal"),
    ("refresh", "auth_drafts"): (
        f"{_T}.entries.auth_drafts.refresh",
        "refresh_auth_drafts",
    ),
    ("refresh", "benchmark"): (f"{_T}.entries.benchmark.refresh", "refresh_benchmark"),
    ("refresh", "benchmark_test"): (
        f"{_T}.entries.benchmark_test.refresh",
        "refresh_benchmark_test",
    ),
    ("refresh", "call_uploads"): (
        f"{_T}.entries.call_uploads.refresh",
        "refresh_call_uploads",
    ),
    ("refresh", "calls"): (f"{_T}.entries.calls.refresh", "refresh_calls_internal"),
    ("refresh", "chat"): (f"{_T}.entries.chat.refresh", "refresh_chat"),
    ("refresh", "chat_drafts"): (
        f"{_T}.entries.chat_drafts.refresh",
        "refresh_chat_drafts",
    ),
    ("refresh", "cohort_drafts"): (
        f"{_T}.entries.cohort_drafts.refresh",
        "refresh_cohort_drafts",
    ),
    ("refresh", "department_drafts"): (
        f"{_T}.entries.department_drafts.refresh",
        "refresh_department_drafts",
    ),
    ("refresh", "document_drafts"): (
        f"{_T}.entries.document_drafts.refresh",
        "refresh_document_drafts",
    ),
    ("refresh", "emulations"): (
        f"{_T}.entries.emulations.refresh",
        "refresh_emulations",
    ),
    ("refresh", "eval_drafts"): (
        f"{_T}.entries.eval_drafts.refresh",
        "refresh_eval_drafts",
    ),
    ("refresh", "field_drafts"): (
        f"{_T}.entries.field_drafts.refresh",
        "refresh_field_drafts",
    ),
    ("refresh", "file_uploads"): (
        f"{_T}.entries.file_uploads.refresh",
        "refresh_file_uploads",
    ),
    ("refresh", "files"): (f"{_T}.entries.files.refresh", "refresh_files_internal"),
    ("refresh", "grant_consumptions"): (
        f"{_T}.entries.grant_consumptions.refresh",
        "refresh_grant_consumptions",
    ),
    ("refresh", "grants"): (f"{_T}.entries.grants.refresh", "refresh_grants_internal"),
    ("refresh", "groups"): (f"{_T}.entries.groups.refresh", "refresh_groups"),
    ("refresh", "health"): (f"{_T}.entries.health.refresh", "refresh_health_internal"),
    ("refresh", "home"): (f"{_T}.entries.home.refresh", "refresh_home"),
    ("refresh", "home_chat"): (f"{_T}.entries.home_chat.refresh", "refresh_home_chat"),
    ("refresh", "image_uploads"): (
        f"{_T}.entries.image_uploads.refresh",
        "refresh_image_uploads",
    ),
    ("refresh", "images"): (f"{_T}.entries.images.refresh", "refresh_images_internal"),
    ("refresh", "invocation"): (
        f"{_T}.entries.invocation.refresh",
        "refresh_invocations",
    ),
    ("refresh", "invocation_drafts"): (
        f"{_T}.entries.invocation_drafts.refresh",
        "refresh_invocation_drafts",
    ),
    ("refresh", "logins"): (f"{_T}.entries.logins.refresh", "refresh_logins"),
    ("refresh", "message_uploads"): (
        f"{_T}.entries.message_uploads.refresh",
        "refresh_message_uploads",
    ),
    ("refresh", "messages"): (
        f"{_T}.entries.messages.refresh",
        "refresh_messages_internal",
    ),
    ("refresh", "attempt_message_completion"): (
        f"{_T}.entries.attempt_message_completion.refresh",
        "refresh_attempt_message_completion",
    ),
    ("refresh", "metrics"): (
        f"{_T}.entries.metrics.refresh",
        "refresh_metrics_internal",
    ),
    ("refresh", "model_drafts"): (
        f"{_T}.entries.model_drafts.refresh",
        "refresh_model_drafts",
    ),
    ("refresh", "parameter_drafts"): (
        f"{_T}.entries.parameter_drafts.refresh",
        "refresh_parameter_drafts",
    ),
    ("refresh", "persona"): (
        f"{_T}.entries.persona.refresh",
        "refresh_persona_internal",
    ),
    ("refresh", "persona_drafts"): (
        f"{_T}.entries.persona_drafts.refresh",
        "refresh_persona_drafts",
    ),
    ("refresh", "personas"): (f"{_T}.entries.personas.refresh", "refresh_personas"),
    ("refresh", "practice"): (f"{_T}.entries.practice.refresh", "refresh_practice"),
    ("refresh", "practice_chat"): (
        f"{_T}.entries.practice_chat.refresh",
        "refresh_practice_chat",
    ),
    ("refresh", "problems"): (f"{_T}.entries.problems.refresh", "refresh_problems"),
    ("refresh", "profile_drafts"): (
        f"{_T}.entries.profile_drafts.refresh",
        "refresh_profile_drafts",
    ),
    ("refresh", "provider_drafts"): (
        f"{_T}.entries.provider_drafts.refresh",
        "refresh_provider_drafts",
    ),
    ("refresh", "resolves"): (f"{_T}.entries.resolves.refresh", "refresh_resolves"),
    ("refresh", "rubric_drafts"): (
        f"{_T}.entries.rubric_drafts.refresh",
        "refresh_rubric_drafts",
    ),
    ("refresh", "run_pricing"): (
        f"{_T}.entries.run_pricing.refresh",
        "refresh_run_pricing_internal",
    ),
    ("refresh", "runs"): (f"{_T}.entries.runs.refresh", "refresh_runs_internal"),
    ("refresh", "scenario_drafts"): (
        f"{_T}.entries.scenario_drafts.refresh",
        "refresh_scenario_drafts",
    ),
    ("refresh", "sessions"): (f"{_T}.entries.sessions.refresh", "refresh_sessions"),
    ("refresh", "setting_drafts"): (
        f"{_T}.entries.setting_drafts.refresh",
        "refresh_setting_drafts",
    ),
    ("refresh", "simulation_drafts"): (
        f"{_T}.entries.simulation_drafts.refresh",
        "refresh_simulation_drafts",
    ),
    ("refresh", "test"): (f"{_T}.entries.test.refresh", "refresh_test"),
    ("refresh", "test_archive"): (
        f"{_T}.entries.test_archive.refresh",
        "refresh_test_archive",
    ),
    ("refresh", "test_invocation_completion"): (
        f"{_T}.entries.test_invocation_completion.refresh",
        "refresh_test_invocation_completion",
    ),
    ("refresh", "test_feedback"): (
        f"{_T}.entries.test_feedback.refresh",
        "refresh_test_feedback",
    ),
    ("refresh", "test_grade"): (
        f"{_T}.entries.test_grade.refresh",
        "refresh_test_grade",
    ),
    ("refresh", "test_invocation"): (
        f"{_T}.entries.test_invocation.refresh",
        "refresh_test_invocation",
    ),
    ("refresh", "test_invocation_bridge"): (
        f"{_T}.entries.test_invocation_bridge.refresh",
        "refresh_test_invocation_bridge",
    ),
    ("refresh", "test_invocation_groups"): (
        f"{_T}.entries.test_invocation_groups.refresh",
        "refresh_test_invocation_groups",
    ),
    ("refresh", "test_invocation_runs"): (
        f"{_T}.entries.test_invocation_runs.refresh",
        "refresh_test_invocation_runs",
    ),
    ("refresh", "text_uploads"): (
        f"{_T}.entries.text_uploads.refresh",
        "refresh_text_uploads",
    ),
    ("refresh", "texts"): (f"{_T}.entries.texts.refresh", "refresh_texts_internal"),
    ("refresh", "tokens"): (f"{_T}.entries.tokens.refresh", "refresh_tokens"),
    ("refresh", "tool_drafts"): (
        f"{_T}.entries.tool_drafts.refresh",
        "refresh_tool_drafts",
    ),
    ("refresh", "uploads"): (
        f"{_T}.entries.uploads.refresh",
        "refresh_uploads_internal",
    ),
    ("refresh", "upload_completion"): (
        f"{_T}.entries.upload_completion.refresh",
        "refresh_upload_completion",
    ),
    ("refresh", "video_uploads"): (
        f"{_T}.entries.video_uploads.refresh",
        "refresh_video_uploads",
    ),
    ("refresh", "videos"): (f"{_T}.entries.videos.refresh", "refresh_videos_internal"),
    # search
    ("search", "activity"): (f"{_T}.entries.activity.search", "search_activity"),
    ("search", "agent_drafts"): (
        f"{_T}.entries.agent_drafts.search",
        "search_agent_drafts",
    ),
    ("search", "attempt"): (f"{_T}.entries.attempt.search", "search_attempts"),
    ("search", "attempt_analysis"): (
        f"{_T}.entries.attempt_analysis.search",
        "search_attempt_analyses",
    ),
    ("search", "attempt_archive"): (
        f"{_T}.entries.attempt_archive.search",
        "search_attempt_archives",
    ),
    ("search", "attempt_chat"): (
        f"{_T}.entries.attempt_chat.search",
        "search_attempt_chats",
    ),
    ("search", "attempt_chat_bridge"): (
        f"{_T}.entries.attempt_chat_bridge.search",
        "search_attempt_chat_bridges",
    ),
    ("search", "attempt_chat_completion"): (
        f"{_T}.entries.attempt_chat_completion.search",
        "search_attempt_chat_completions",
    ),
    ("search", "attempt_content"): (
        f"{_T}.entries.attempt_content.search",
        "search_attempt_contents",
    ),
    ("search", "attempt_conversation_completion"): (
        f"{_T}.entries.attempt_conversation_completion.search",
        "search_attempt_conversation_completions",
    ),
    ("search", "attempt_conversations"): (
        f"{_T}.entries.attempt_conversations.search",
        "search_attempt_conversations",
    ),
    ("search", "attempt_feedback"): (
        f"{_T}.entries.attempt_feedback.search",
        "search_attempt_feedback_entries",
    ),
    ("search", "attempt_grade"): (
        f"{_T}.entries.attempt_grade.search",
        "search_attempt_grades",
    ),
    ("search", "attempt_highlight"): (
        f"{_T}.entries.attempt_highlight.search",
        "search_attempt_highlights",
    ),
    ("search", "attempt_hint"): (
        f"{_T}.entries.attempt_hint.search",
        "search_attempt_hints",
    ),
    ("search", "attempt_home"): (
        f"{_T}.entries.attempt_home.search",
        "search_attempt_homes",
    ),
    ("search", "attempt_improvement"): (
        f"{_T}.entries.attempt_improvement.search",
        "search_attempt_improvements",
    ),
    ("search", "attempt_message"): (
        f"{_T}.entries.attempt_message.search",
        "search_attempt_messages",
    ),
    ("search", "attempt_message_tree"): (
        f"{_T}.entries.attempt_message_tree.search",
        "search_attempt_message_trees",
    ),
    ("search", "attempt_mutes"): (
        f"{_T}.entries.attempt_mutes.search",
        "search_attempt_mutes_entries_internal",
    ),
    ("search", "attempt_practice"): (
        f"{_T}.entries.attempt_practice.search",
        "search_attempt_practice_entries",
    ),
    ("search", "attempt_replacement"): (
        f"{_T}.entries.attempt_replacement.search",
        "search_attempt_replacements",
    ),
    ("search", "attempt_responses"): (
        f"{_T}.entries.attempt_responses.search",
        "search_attempt_responses",
    ),
    ("search", "attempt_strength"): (
        f"{_T}.entries.attempt_strength.search",
        "search_attempt_strengths",
    ),
    ("search", "audio_uploads"): (
        f"{_T}.entries.audio_uploads.search",
        "search_audio_uploads",
    ),
    ("search", "audios"): (f"{_T}.entries.audios.search", "search_audios"),
    ("search", "auth_drafts"): (
        f"{_T}.entries.auth_drafts.search",
        "search_auth_drafts",
    ),
    ("search", "benchmark"): (f"{_T}.entries.benchmark.search", "search_benchmarks"),
    ("search", "benchmark_test"): (
        f"{_T}.entries.benchmark_test.search",
        "search_benchmark_tests",
    ),
    ("search", "call_uploads"): (
        f"{_T}.entries.call_uploads.search",
        "search_call_uploads",
    ),
    ("search", "calls"): (f"{_T}.entries.calls.search", "search_calls"),
    ("search", "chat"): (f"{_T}.entries.chat.search", "search_chat_entries_internal"),
    ("search", "chat_drafts"): (
        f"{_T}.entries.chat_drafts.search",
        "search_chat_drafts",
    ),
    ("search", "cohort_drafts"): (
        f"{_T}.entries.cohort_drafts.search",
        "search_cohort_drafts",
    ),
    ("search", "department_drafts"): (
        f"{_T}.entries.department_drafts.search",
        "search_department_drafts",
    ),
    ("search", "document_drafts"): (
        f"{_T}.entries.document_drafts.search",
        "search_document_drafts",
    ),
    ("search", "emulations"): (f"{_T}.entries.emulations.search", "search_emulations"),
    ("search", "eval_drafts"): (
        f"{_T}.entries.eval_drafts.search",
        "search_eval_drafts",
    ),
    ("search", "field_drafts"): (
        f"{_T}.entries.field_drafts.search",
        "search_field_drafts",
    ),
    ("search", "file_uploads"): (
        f"{_T}.entries.file_uploads.search",
        "search_file_uploads",
    ),
    ("search", "files"): (f"{_T}.entries.files.search", "search_files"),
    ("search", "grant_consumptions"): (
        f"{_T}.entries.grant_consumptions.search",
        "search_grant_consumptions",
    ),
    ("search", "grants"): (f"{_T}.entries.grants.search", "search_grants"),
    ("search", "groups"): (f"{_T}.entries.groups.search", "search_groups"),
    ("search", "health"): (f"{_T}.entries.health.search", "search_health"),
    ("search", "home"): (f"{_T}.entries.home.search", "search_homes"),
    ("search", "home_chat"): (f"{_T}.entries.home_chat.search", "search_home_chats"),
    ("search", "image_uploads"): (
        f"{_T}.entries.image_uploads.search",
        "search_image_uploads",
    ),
    ("search", "images"): (f"{_T}.entries.images.search", "search_images"),
    ("search", "invocation"): (f"{_T}.entries.invocation.search", "search_invocations"),
    ("search", "invocation_drafts"): (
        f"{_T}.entries.invocation_drafts.search",
        "search_invocation_drafts",
    ),
    ("search", "logins"): (f"{_T}.entries.logins.search", "search_logins"),
    ("search", "message_uploads"): (
        f"{_T}.entries.message_uploads.search",
        "search_message_uploads",
    ),
    ("search", "messages"): (f"{_T}.entries.messages.search", "search_messages"),
    ("search", "attempt_message_completion"): (
        f"{_T}.entries.attempt_message_completion.search",
        "search_attempt_message_completions",
    ),
    ("search", "metrics"): (f"{_T}.entries.metrics.search", "search_metrics"),
    ("search", "model_drafts"): (
        f"{_T}.entries.model_drafts.search",
        "search_model_drafts",
    ),
    ("search", "parameter_drafts"): (
        f"{_T}.entries.parameter_drafts.search",
        "search_parameter_drafts",
    ),
    ("search", "persona"): (f"{_T}.entries.persona.search", "search_personas"),
    ("search", "persona_drafts"): (
        f"{_T}.entries.persona_drafts.search",
        "search_persona_drafts",
    ),
    ("search", "personas"): (f"{_T}.entries.personas.search", "search_personas"),
    ("search", "practice"): (f"{_T}.entries.practice.search", "search_practices"),
    ("search", "practice_chat"): (
        f"{_T}.entries.practice_chat.search",
        "search_practice_chats",
    ),
    ("search", "problems"): (f"{_T}.entries.problems.search", "search_problems"),
    ("search", "profile_drafts"): (
        f"{_T}.entries.profile_drafts.search",
        "search_profile_drafts",
    ),
    ("search", "provider_drafts"): (
        f"{_T}.entries.provider_drafts.search",
        "search_provider_drafts",
    ),
    ("search", "resolves"): (f"{_T}.entries.resolves.search", "search_resolves"),
    ("search", "rubric_drafts"): (
        f"{_T}.entries.rubric_drafts.search",
        "search_rubric_drafts",
    ),
    ("search", "run_pricing"): (
        f"{_T}.entries.run_pricing.search",
        "search_run_pricing_entries_internal",
    ),
    ("search", "runs"): (f"{_T}.entries.runs.search", "search_runs"),
    ("search", "scenario_drafts"): (
        f"{_T}.entries.scenario_drafts.search",
        "search_scenario_drafts",
    ),
    ("search", "sessions"): (f"{_T}.entries.sessions.search", "search_sessions"),
    ("search", "setting_drafts"): (
        f"{_T}.entries.setting_drafts.search",
        "search_setting_drafts",
    ),
    ("search", "simulation_drafts"): (
        f"{_T}.entries.simulation_drafts.search",
        "search_simulation_drafts",
    ),
    ("search", "test"): (f"{_T}.entries.test.search", "search_tests"),
    ("search", "test_archive"): (
        f"{_T}.entries.test_archive.search",
        "search_test_archives",
    ),
    ("search", "test_invocation_completion"): (
        f"{_T}.entries.test_invocation_completion.search",
        "search_test_invocation_completions",
    ),
    ("search", "test_feedback"): (
        f"{_T}.entries.test_feedback.search",
        "search_test_feedback_entries",
    ),
    ("search", "test_grade"): (f"{_T}.entries.test_grade.search", "search_test_grades"),
    ("search", "test_invocation"): (
        f"{_T}.entries.test_invocation.search",
        "search_test_invocation_entries_internal",
    ),
    ("search", "test_invocation_bridge"): (
        f"{_T}.entries.test_invocation_bridge.search",
        "search_test_invocation_bridge",
    ),
    ("search", "test_invocation_groups"): (
        f"{_T}.entries.test_invocation_groups.search",
        "search_test_invocation_groups",
    ),
    ("search", "test_invocation_runs"): (
        f"{_T}.entries.test_invocation_runs.search",
        "search_test_invocation_runs",
    ),
    ("search", "text_uploads"): (
        f"{_T}.entries.text_uploads.search",
        "search_text_uploads",
    ),
    ("search", "texts"): (f"{_T}.entries.texts.search", "search_texts"),
    ("search", "tokens"): (f"{_T}.entries.tokens.search", "search_tokens"),
    ("search", "tool_drafts"): (
        f"{_T}.entries.tool_drafts.search",
        "search_tool_drafts",
    ),
    ("search", "uploads"): (f"{_T}.entries.uploads.search", "search_uploads"),
    ("search", "upload_completion"): (
        f"{_T}.entries.upload_completion.search",
        "search_upload_completions",
    ),
    ("search", "video_uploads"): (
        f"{_T}.entries.video_uploads.search",
        "search_video_uploads",
    ),
    ("search", "videos"): (f"{_T}.entries.videos.search", "search_videos"),
    # docs
    ("docs", "activity"): (f"{_T}.entries.activity.docs", "get_activity_docs"),
    ("docs", "agent_drafts"): (
        f"{_T}.entries.agent_drafts.docs",
        "get_agent_drafts_docs",
    ),
    ("docs", "attempt"): (f"{_T}.entries.attempt.docs", "get_attempt_docs"),
    ("docs", "attempt_analysis"): (
        f"{_T}.entries.attempt_analysis.docs",
        "get_attempt_analysis_docs",
    ),
    ("docs", "attempt_archive"): (
        f"{_T}.entries.attempt_archive.docs",
        "get_attempt_archive_docs",
    ),
    ("docs", "attempt_chat"): (
        f"{_T}.entries.attempt_chat.docs",
        "get_attempt_chat_docs",
    ),
    ("docs", "attempt_chat_bridge"): (
        f"{_T}.entries.attempt_chat_bridge.docs",
        "get_attempt_chat_bridge_docs",
    ),
    ("docs", "attempt_chat_completion"): (
        f"{_T}.entries.attempt_chat_completion.docs",
        "get_attempt_chat_completion_docs",
    ),
    ("docs", "attempt_content"): (
        f"{_T}.entries.attempt_content.docs",
        "get_attempt_content_docs",
    ),
    ("docs", "attempt_conversation_completion"): (
        f"{_T}.entries.attempt_conversation_completion.docs",
        "get_attempt_conversation_completion_docs",
    ),
    ("docs", "attempt_conversations"): (
        f"{_T}.entries.attempt_conversations.docs",
        "get_attempt_conversations_docs",
    ),
    ("docs", "attempt_feedback"): (
        f"{_T}.entries.attempt_feedback.docs",
        "get_attempt_feedback_docs",
    ),
    ("docs", "attempt_grade"): (
        f"{_T}.entries.attempt_grade.docs",
        "get_attempt_grade_docs",
    ),
    ("docs", "attempt_highlight"): (
        f"{_T}.entries.attempt_highlight.docs",
        "get_attempt_highlight_docs",
    ),
    ("docs", "attempt_hint"): (
        f"{_T}.entries.attempt_hint.docs",
        "get_attempt_hint_docs",
    ),
    ("docs", "attempt_home"): (
        f"{_T}.entries.attempt_home.docs",
        "get_attempt_home_docs",
    ),
    ("docs", "attempt_improvement"): (
        f"{_T}.entries.attempt_improvement.docs",
        "get_attempt_improvement_docs",
    ),
    ("docs", "attempt_message"): (
        f"{_T}.entries.attempt_message.docs",
        "get_attempt_message_docs",
    ),
    ("docs", "attempt_message_tree"): (
        f"{_T}.entries.attempt_message_tree.docs",
        "get_attempt_message_tree_docs",
    ),
    ("docs", "attempt_mutes"): (
        f"{_T}.entries.attempt_mutes.docs",
        "get_attempt_mutes_docs",
    ),
    ("docs", "attempt_practice"): (
        f"{_T}.entries.attempt_practice.docs",
        "get_attempt_practice_docs",
    ),
    ("docs", "attempt_replacement"): (
        f"{_T}.entries.attempt_replacement.docs",
        "get_attempt_replacement_docs",
    ),
    ("docs", "attempt_responses"): (
        f"{_T}.entries.attempt_responses.docs",
        "get_attempt_responses_docs",
    ),
    ("docs", "attempt_strength"): (
        f"{_T}.entries.attempt_strength.docs",
        "get_attempt_strength_docs",
    ),
    ("docs", "audio_uploads"): (
        f"{_T}.entries.audio_uploads.docs",
        "get_audio_uploads_docs",
    ),
    ("docs", "audios"): (f"{_T}.entries.audios.docs", "get_audios_docs"),
    ("docs", "auth_drafts"): (f"{_T}.entries.auth_drafts.docs", "get_auth_drafts_docs"),
    ("docs", "benchmark"): (f"{_T}.entries.benchmark.docs", "get_benchmark_docs"),
    ("docs", "benchmark_test"): (
        f"{_T}.entries.benchmark_test.docs",
        "get_benchmark_test_docs",
    ),
    ("docs", "call_uploads"): (
        f"{_T}.entries.call_uploads.docs",
        "get_call_uploads_docs",
    ),
    ("docs", "calls"): (f"{_T}.entries.calls.docs", "get_calls_docs"),
    ("docs", "chat"): (f"{_T}.entries.chat.docs", "get_chat_docs"),
    ("docs", "chat_drafts"): (f"{_T}.entries.chat_drafts.docs", "get_chat_drafts_docs"),
    ("docs", "cohort_drafts"): (
        f"{_T}.entries.cohort_drafts.docs",
        "get_cohort_drafts_docs",
    ),
    ("docs", "department_drafts"): (
        f"{_T}.entries.department_drafts.docs",
        "get_department_drafts_docs",
    ),
    ("docs", "document_drafts"): (
        f"{_T}.entries.document_drafts.docs",
        "get_document_drafts_docs",
    ),
    ("docs", "emulations"): (f"{_T}.entries.emulations.docs", "get_emulations_docs"),
    ("docs", "eval_drafts"): (f"{_T}.entries.eval_drafts.docs", "get_eval_drafts_docs"),
    ("docs", "field_drafts"): (
        f"{_T}.entries.field_drafts.docs",
        "get_field_drafts_docs",
    ),
    ("docs", "file_uploads"): (
        f"{_T}.entries.file_uploads.docs",
        "get_file_uploads_docs",
    ),
    ("docs", "files"): (f"{_T}.entries.files.docs", "get_files_docs"),
    ("docs", "grant_consumptions"): (
        f"{_T}.entries.grant_consumptions.docs",
        "get_grant_consumptions_docs",
    ),
    ("docs", "grants"): (f"{_T}.entries.grants.docs", "get_grants_docs"),
    ("docs", "groups"): (f"{_T}.entries.groups.docs", "get_groups_docs"),
    ("docs", "health"): (f"{_T}.entries.health.docs", "get_health_docs"),
    ("docs", "home"): (f"{_T}.entries.home.docs", "get_home_docs"),
    ("docs", "home_chat"): (f"{_T}.entries.home_chat.docs", "get_home_chat_docs"),
    ("docs", "image_uploads"): (
        f"{_T}.entries.image_uploads.docs",
        "get_image_uploads_docs",
    ),
    ("docs", "images"): (f"{_T}.entries.images.docs", "get_images_docs"),
    ("docs", "invocation"): (f"{_T}.entries.invocation.docs", "get_invocation_docs"),
    ("docs", "invocation_drafts"): (
        f"{_T}.entries.invocation_drafts.docs",
        "get_invocation_drafts_docs",
    ),
    ("docs", "logins"): (f"{_T}.entries.logins.docs", "get_logins_docs"),
    ("docs", "message_uploads"): (
        f"{_T}.entries.message_uploads.docs",
        "get_message_uploads_docs",
    ),
    ("docs", "messages"): (f"{_T}.entries.messages.docs", "get_messages_docs"),
    # messages_completions removed — replaced by attempt_message_completion
    ("docs", "metrics"): (f"{_T}.entries.metrics.docs", "get_metrics_docs"),
    ("docs", "model_drafts"): (
        f"{_T}.entries.model_drafts.docs",
        "get_model_drafts_docs",
    ),
    ("docs", "parameter_drafts"): (
        f"{_T}.entries.parameter_drafts.docs",
        "get_parameter_drafts_docs",
    ),
    ("docs", "persona"): (f"{_T}.entries.persona.docs", "get_persona_docs"),
    ("docs", "persona_drafts"): (
        f"{_T}.entries.persona_drafts.docs",
        "get_persona_drafts_docs",
    ),
    ("docs", "personas"): (f"{_T}.entries.personas.docs", "get_personas_docs"),
    ("docs", "practice"): (f"{_T}.entries.practice.docs", "get_practice_docs"),
    ("docs", "practice_chat"): (
        f"{_T}.entries.practice_chat.docs",
        "get_practice_chat_docs",
    ),
    ("docs", "problems"): (f"{_T}.entries.problems.docs", "get_problems_docs"),
    ("docs", "profile_drafts"): (
        f"{_T}.entries.profile_drafts.docs",
        "get_profile_drafts_docs",
    ),
    ("docs", "provider_drafts"): (
        f"{_T}.entries.provider_drafts.docs",
        "get_provider_drafts_docs",
    ),
    ("docs", "resolves"): (f"{_T}.entries.resolves.docs", "get_resolves_docs"),
    ("docs", "rubric_drafts"): (
        f"{_T}.entries.rubric_drafts.docs",
        "get_rubric_drafts_docs",
    ),
    ("docs", "run_pricing"): (f"{_T}.entries.run_pricing.docs", "get_run_pricing_docs"),
    ("docs", "runs"): (f"{_T}.entries.runs.docs", "get_runs_docs"),
    ("docs", "scenario_drafts"): (
        f"{_T}.entries.scenario_drafts.docs",
        "get_scenario_drafts_docs",
    ),
    ("docs", "sessions"): (f"{_T}.entries.sessions.docs", "get_sessions_docs"),
    ("docs", "setting_drafts"): (
        f"{_T}.entries.setting_drafts.docs",
        "get_setting_drafts_docs",
    ),
    ("docs", "simulation_drafts"): (
        f"{_T}.entries.simulation_drafts.docs",
        "get_simulation_drafts_docs",
    ),
    ("docs", "test"): (f"{_T}.entries.test.docs", "get_test_docs"),
    ("docs", "test_archive"): (
        f"{_T}.entries.test_archive.docs",
        "get_test_archive_docs",
    ),
    ("docs", "test_invocation_completion"): (
        f"{_T}.entries.test_invocation_completion.docs",
        "get_test_invocation_completion_docs",
    ),
    ("docs", "test_feedback"): (
        f"{_T}.entries.test_feedback.docs",
        "get_test_feedback_docs",
    ),
    ("docs", "test_grade"): (f"{_T}.entries.test_grade.docs", "get_test_grade_docs"),
    ("docs", "test_invocation"): (
        f"{_T}.entries.test_invocation.docs",
        "get_test_invocation_docs",
    ),
    ("docs", "test_invocation_bridge"): (
        f"{_T}.entries.test_invocation_bridge.docs",
        "get_test_invocation_bridge_docs",
    ),
    ("docs", "test_invocation_groups"): (
        f"{_T}.entries.test_invocation_groups.docs",
        "get_test_invocation_groups_docs",
    ),
    ("docs", "test_invocation_runs"): (
        f"{_T}.entries.test_invocation_runs.docs",
        "get_test_invocation_runs_docs",
    ),
    ("docs", "text_uploads"): (
        f"{_T}.entries.text_uploads.docs",
        "get_text_uploads_docs",
    ),
    ("docs", "texts"): (f"{_T}.entries.texts.docs", "get_texts_docs"),
    ("docs", "tokens"): (f"{_T}.entries.tokens.docs", "get_tokens_docs"),
    ("docs", "tool_drafts"): (f"{_T}.entries.tool_drafts.docs", "get_tool_drafts_docs"),
    ("docs", "uploads"): (f"{_T}.entries.uploads.docs", "get_uploads_docs"),
    ("docs", "upload_completion"): (
        f"{_T}.entries.upload_completion.docs",
        "get_upload_completion_docs",
    ),
    ("docs", "video_uploads"): (
        f"{_T}.entries.video_uploads.docs",
        "get_video_uploads_docs",
    ),
    ("docs", "videos"): (f"{_T}.entries.videos.docs", "get_videos_docs"),
}

# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------

_REGISTRIES: dict[str, dict[tuple[str, str], tuple[str, str]]] = {
    "artifact": ARTIFACT_TOOL_FNS,
    "resource": RESOURCE_TOOL_FNS,
    "entry": ENTRY_TOOL_FNS,
}
