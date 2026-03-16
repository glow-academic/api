"""Generate system prompt and instruction template files for all 34 artifacts.

Resources are derived from actual DB junction/connection tables.
Tool names match intended state (create_{resource} / use_{resource}).
"""

import os

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# CRUD artifacts — resources from {artifact}_{resource}_junction tables
# Self-ref junctions excluded (e.g. agent_agents_junction)
# ---------------------------------------------------------------------------

CRUD_ARTIFACTS = {
    "agent": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("models", "model binding (model_id)"),
            ("prompts", "system prompt (system_prompt text)"),
            ("instructions", "instruction template (template text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("tools", "tool binding (tool_id)"),
            ("temperature_levels", "temperature level (level)"),
            ("reasoning_levels", "reasoning level (level)"),
            ("voices", "voice setting (voice)"),
        ],
        "desc": "AI agents with models, prompts, instructions, and tool bindings",
    },
    "auth": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("items", "auth item (item configuration)"),
            ("protocols", "auth protocol (protocol type)"),
            ("slugs", "URL slug (slug text)"),
        ],
        "desc": "authentication configurations with protocols, slugs, and items",
    },
    "persona": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("colors", "color (name, description, hex_code)"),
            ("icons", "icon (name, value)"),
            ("instructions", "behavioral instruction (template text)"),
            ("flags", "flag setting (flag value)"),
            ("examples", "example behavior (example text)"),
            ("parameter_fields", "parameter field link (field_id, parameter_id)"),
            ("departments", "department assignment (department_id)"),
            ("parameters", "parameter binding (parameter_id)"),
        ],
        "desc": "personas for AI-powered simulations and interactions",
    },
    "scenario": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("documents", "reference document (document_id)"),
            ("images", "image (image reference)"),
            ("objectives", "learning objective (objective text)"),
            ("options", "response option (option text)"),
            ("parameter_fields", "parameter field link (field_id, parameter_id)"),
            ("parameters", "parameter binding (parameter_id)"),
            ("personas", "persona binding (persona_id)"),
            ("problem_statements", "problem statement (statement text)"),
            ("questions", "question (question text, options)"),
            ("videos", "video (video reference)"),
        ],
        "desc": "training scenarios with problem statements, objectives, questions, and persona assignments",
    },
    "simulation": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("scenarios", "scenario binding (scenario_id)"),
            ("scenario_flags", "scenario flag override (flag value per scenario)"),
            (
                "scenario_personas",
                "scenario persona override (persona_id per scenario)",
            ),
            ("scenario_positions", "scenario ordering (position per scenario)"),
            ("scenario_rubrics", "scenario rubric binding (rubric_id per scenario)"),
            ("scenario_time_limits", "scenario time limit (minutes per scenario)"),
        ],
        "desc": "simulation configurations with scenario orderings, rubrics, and time limits",
    },
    "cohort": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("simulations", "simulation binding (simulation_id)"),
            ("simulation_positions", "simulation ordering (position)"),
            ("simulation_availability", "simulation availability window (start, end)"),
        ],
        "desc": "cohorts grouping simulations for training programs",
    },
    "document": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("images", "image (image reference)"),
            ("parameter_fields", "parameter field link (field_id, parameter_id)"),
            ("parameters", "parameter binding (parameter_id)"),
            ("texts", "text content (text body)"),
            ("uploads", "file upload (upload reference)"),
        ],
        "desc": "documents with uploads, images, text content, and parameter fields",
    },
    "profile": {
        "resources": [
            ("names", "name (name text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("emails", "email address (email text)"),
            ("cohorts", "cohort enrollment (cohort_id)"),
            ("request_limits", "request limit (limit value)"),
            ("roles", "role assignment (role type)"),
        ],
        "desc": "user profiles with department assignments, cohort enrollments, and roles",
    },
    "parameter": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("fields", "field binding (field_id)"),
        ],
        "desc": "parameters with associated fields for dynamic configuration",
    },
    "field": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            (
                "conditional_parameters",
                "conditional parameter rule (parameter_id, condition)",
            ),
        ],
        "desc": "fields with conditional parameter logic for dynamic forms",
    },
    "model": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("values", "model identifier (value text)"),
            ("providers", "provider binding (provider_id)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("modalities", "modality (modality type)"),
            ("temperature_levels", "temperature level (level)"),
            ("pricing", "pricing tier (pricing configuration)"),
            ("reasoning_levels", "reasoning level (level)"),
            ("qualities", "quality tier (quality level)"),
            ("voices", "voice setting (voice)"),
        ],
        "desc": "AI model configurations with providers, modalities, pricing, and capabilities",
    },
    "tool": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("args", "argument definition (name, type, description)"),
            ("arg_positions", "argument ordering (position)"),
            ("args_outputs", "argument output mapping (output configuration)"),
            ("bindings", "entry type binding (entry_type)"),
            ("domains", "domain scope (domain name)"),
        ],
        "desc": "tool definitions with arguments, output mappings, entry bindings, and domain scopes",
    },
    "department": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("settings", "department setting (setting configuration)"),
        ],
        "desc": "organizational departments with settings",
    },
    "provider": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("values", "provider identifier (value text)"),
            ("endpoints", "API endpoint (endpoint URL)"),
            ("keys", "API key (key configuration)"),
        ],
        "desc": "AI provider configurations with endpoints and API keys",
    },
    "rubric": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("points", "point value (points number)"),
            ("standard_groups", "standard group (group name, description)"),
            ("standards", "standard (standard definition, criteria)"),
        ],
        "desc": "grading rubrics with standard groups, standards, and point values",
    },
    "eval": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("runs", "evaluation run (run configuration)"),
            ("run_positions", "run ordering (position)"),
            ("runs_rubrics", "run rubric binding (rubric_id per run)"),
            ("groups", "evaluation group (group configuration)"),
            ("group_positions", "group ordering (position)"),
            ("groups_rubrics", "group rubric binding (rubric_id per group)"),
        ],
        "desc": "evaluation configurations with runs, groups, and rubric bindings",
    },
    "setting": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("colors", "theme color (name, hex_code)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("agents", "system agent binding (agent_id)"),
            ("auths", "auth configuration binding (auth_id)"),
            ("auth_item_keys", "auth item key (key configuration)"),
            ("auth_values", "auth value setting (value)"),
            ("profiles", "profile binding (profile_id)"),
            ("provider_keys", "provider API key (key configuration)"),
            ("thresholds", "threshold setting (threshold value)"),
        ],
        "desc": "system settings with auth, provider keys, thresholds, and department assignments",
    },
    # --- Chat and Invocation use CRUD pattern (from connection tables) ---
    "chat": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("personas", "persona binding (persona_id)"),
            ("documents", "reference document (document_id)"),
            ("scenarios", "scenario binding (scenario_id)"),
            ("parameter_fields", "parameter field link (field_id, parameter_id)"),
            ("parameters", "parameter binding (parameter_id)"),
            ("fields", "field value (field_id)"),
            ("questions", "scenario question (question text)"),
            ("options", "response option (option text)"),
            ("videos", "video reference (video_id)"),
            ("images", "image reference (image_id)"),
            ("objectives", "learning objective (objective text)"),
            ("problem_statements", "problem statement (statement text)"),
        ],
        "desc": "training chat sessions with persona-driven scenario conversations",
    },
    "invocation": {
        "resources": [
            ("names", "name (name text)"),
            ("descriptions", "description (description text)"),
            ("flags", "flag setting (flag value)"),
            ("departments", "department assignment (department_id)"),
            ("models", "model binding (model_id)"),
            ("prompts", "system prompt (system_prompt text)"),
            ("instructions", "instruction template (template text)"),
            ("runs", "evaluation run (run_id)"),
            ("groups", "evaluation group (group_id)"),
            ("keys", "API key binding (key_id)"),
            ("tools", "tool binding (tool_id)"),
            ("temperature_levels", "temperature level (level)"),
            ("reasoning_levels", "reasoning level (level)"),
            ("voices", "voice setting (voice)"),
        ],
        "desc": "benchmark invocations with model, prompt, and tool configurations for evaluation runs",
    },
}

# ---------------------------------------------------------------------------
# Analytical artifacts — use create_insights tool
# Resources from registry: names, descriptions, flags, departments
# ---------------------------------------------------------------------------

ANALYTICAL_ARTIFACTS = {
    "dashboard": {
        "desc": "high-level organizational dashboard with KPIs, trends, and departmental breakdowns",
        "focus": "key performance indicators, usage trends, department comparisons, and executive summaries",
    },
    "reports": {
        "desc": "detailed analytical reports on training outcomes, completion rates, and performance metrics",
        "focus": "training effectiveness, completion analytics, score distributions, and longitudinal trends",
    },
    "activity": {
        "desc": "real-time and recent activity monitoring across the platform",
        "focus": "recent actions, active sessions, error patterns, and usage spikes",
    },
    "pricing": {
        "desc": "cost analytics for AI model usage, token consumption, and billing breakdowns",
        "focus": "cost per session, model cost comparisons, department spend, and budget projections",
    },
    "health": {
        "desc": "system health monitoring including API latency, error rates, and infrastructure status",
        "focus": "uptime metrics, error rates, latency percentiles, and degradation alerts",
    },
    "leaderboard": {
        "desc": "performance rankings across profiles, departments, and training programs",
        "focus": "score rankings, improvement trajectories, top performers, and competitive analysis",
    },
    "record": {
        "desc": "individual training record detail with session history and performance progression",
        "focus": "session timeline, score trends, rubric breakdowns, and improvement areas per individual",
    },
    "session": {
        "desc": "individual training session analytics with chat-level and attempt-level detail",
        "focus": "conversation quality, rubric adherence, time-on-task, and per-attempt scoring",
    },
    "group": {
        "desc": "group-level analytics aggregating sessions within a training run or cohort group",
        "focus": "group averages, outlier detection, cohort comparisons, and group-level trends",
    },
}

# ---------------------------------------------------------------------------
# Specialized artifacts — entry-type tools, NOT create/use CRUD pattern
# ---------------------------------------------------------------------------

SPECIALIZED_ARTIFACTS = {
    "attempt-chat": {
        "tools": [
            (
                "create_content",
                "Make a persona speak — generate the in-character response as a content block",
            ),
            (
                "create_hint",
                "Create a strategic hint for the user when they are struggling",
            ),
        ],
        "desc": "the conversational portion of a training attempt — the AI acts as the persona conducting the training dialogue",
    },
    "attempt-grade": {
        "tools": [
            (
                "create_feedback",
                "Create a grade for a specific standard group with a 1-5 score and feedback",
            ),
            (
                "create_strength",
                "Highlight what was strong about a specific message with optional text highlights",
            ),
            (
                "create_improvement",
                "Suggest improvements for a specific message with optional strikethrough/replace",
            ),
            (
                "create_analysis",
                "Create an analysis of audio messages from the conversation",
            ),
            (
                "create_highlight",
                "Create a highlight for a notable strength in the simulation",
            ),
            (
                "create_replacement",
                "Create a replacement suggestion for an improvement",
            ),
        ],
        "desc": "the grading/evaluation portion of a training attempt — analyzing performance and providing structured feedback",
    },
    "test": {
        "tools": [
            (
                "create_feedback",
                "Create a grade for a specific standard group with a 1-5 score and feedback",
            ),
        ],
        "desc": "benchmark test grading — evaluating model outputs against rubric standards",
    },
    "benchmark": {
        "tools": [
            ("create_names", "Create a name for the benchmark run"),
            ("create_descriptions", "Create a description for the benchmark run"),
            ("create_instructions", "Create an instruction template"),
            ("create_models", "Create a model configuration"),
            ("create_prompt", "Set the system prompt"),
            ("create_keys", "Create an API key binding"),
            ("create_reasoning_levels", "Create a reasoning level"),
            ("create_temperature_levels", "Create a temperature level"),
            ("create_voices", "Create a voice setting"),
            ("use_names", "Use an existing name by its ID"),
            ("use_descriptions", "Use an existing description by its ID"),
            ("use_flags", "Use an existing flag by its ID"),
            ("use_departments", "Use an existing department by its ID"),
            ("use_instructions", "Use an existing instruction by its ID"),
        ],
        "desc": "benchmark execution running evaluations across model configurations",
    },
    "home": {
        "tools": [],
        "desc": "home page overview for the current user showing available training and recent activity",
    },
    "practice": {
        "tools": [],
        "desc": "practice mode entry point showing available simulations and training options",
    },
}


# ---------------------------------------------------------------------------
# Generator functions
# ---------------------------------------------------------------------------


def write_crud_system(name: str, info: dict) -> str:
    resources = info["resources"]
    desc = info["desc"]

    create_tools = "\n".join(
        f"- **create_{r[0]}**: Create a new {r[1]}" for r in resources
    )
    use_tools = "\n".join(
        f"- **use_{r[0]}**: Use an existing {r[0].rstrip('s') if not r[0].endswith('ss') else r[0]} by its ID"
        for r in resources
    )

    resource_names = ", ".join(r[0] for r in resources)

    return f"""You are a {name} generation agent responsible for creating and managing {desc}.

## Your Role

Generate or update only the requested resource_types for a {name} artifact:
{resource_names}.

You have access to two types of tools that achieve the same result — choose ONE based on whether the resource exists:

### Create Tools (for NEW resources)
Use these when you need to create NEW resource data that does not exist yet:
{create_tools}

### Use Tools (for EXISTING resources)
Use these when you want to use resources that ALREADY EXIST in the available context:
{use_tools}

## Important: Either Create OR Use

For each resource type, you have two options that achieve the same outcome:
1. **Create** a new resource if one does not exist
2. **Use** an existing resource if a suitable one is already available

You only need to do ONE of these operations per resource — not both. Check the available resources first, then decide whether to create new or use existing.

## Guidelines

### Resource Quality
- Create clear, descriptive names that identify the {name}
- Provide detailed descriptions explaining the {name}'s role and characteristics
- Ensure consistency across all {name} elements
- Review available resources in the context FIRST before creating new ones
- Use existing resources when suitable ones are already available (avoids duplicates)
- Create new resources only when nothing suitable exists

### Best Practices
- Operate only on requested resource_types
- Prefer using existing suitable resources before creating new ones
- Do not invent IDs — use IDs provided in context
- Keep outputs deterministic, concise, and production-safe
- Return only valid tool calls and arguments
- Do not output narrative text
"""


def write_crud_instructions(name: str, info: dict) -> str:
    resources = info["resources"]
    draft_key = f"draft_{name}"

    # Build current form state section
    form_blocks = []
    for r_name, _ in resources:
        display = r_name.replace("_", " ").title()
        # Different display logic per resource type
        if r_name == "names":
            iter_var = "name"
            value_expr = "name.name"
        elif r_name == "descriptions":
            iter_var = "desc"
            value_expr = "desc.description[:100]"
        elif r_name == "colors":
            iter_var = "color"
            value_expr = "color.name ~ ' (' ~ color.hex_code ~ ')'"
        elif r_name == "icons":
            iter_var = "icon"
            value_expr = "icon.name ~ ' (' ~ icon.value ~ ')'"
        elif r_name == "instructions":
            iter_var = "inst"
            value_expr = "inst.template[:80]"
        elif r_name == "examples":
            iter_var = "ex"
            value_expr = "ex.example[:50]"
        elif r_name == "prompts":
            iter_var = "p"
            value_expr = "p.system_prompt[:80]"
        elif r_name == "texts":
            iter_var = "t"
            value_expr = "t.text[:80]"
        else:
            iter_var = "item"
            value_expr = "item.name"

        # Derive draft ID key — strip trailing 's' unless double-s
        if r_name.endswith("ies"):
            id_key = r_name  # keep as-is, e.g. modalities
        elif r_name.endswith("ss"):
            id_key = r_name  # e.g. "pass" — keep
        elif r_name.endswith("s"):
            id_key = r_name[:-1]  # names → name, descriptions → description
        else:
            id_key = r_name

        form_blocks.append(
            f"""{{% if {r_name} and {r_name}|length > 0 %}}
**Current {display}:** {{% for {iter_var} in {r_name} %}}{{{{ {value_expr} }}}}{{% if not loop.last %}}, {{% endif %}}{{% endfor %}}
{{% elif draft and draft.{id_key}_ids and draft.{id_key}_ids|length > 0 %}}
**Current {display} IDs:** {{% for id in draft.{id_key}_ids %}}{{{{ id }}}}{{% if not loop.last %}}, {{% endif %}}{{% endfor %}}
{{% else %}}
**Current {display}:** (not selected)
{{% endif %}}"""
        )

    # Build available resources section
    available_blocks = []
    for r_name, _ in resources:
        display = r_name.replace("_", " ").title()
        if r_name == "names":
            line = "- id: {{ item.id }} | name: {{ item.name }}"
        elif r_name == "descriptions":
            line = "- id: {{ item.id }} | description: {{ item.description[:100] }}{% if item.description|length > 100 %}...{% endif %}"
        elif r_name == "colors":
            line = "- id: {{ item.id }} | name: {{ item.name }} | hex_code: {{ item.hex_code }}"
        elif r_name == "icons":
            line = (
                "- id: {{ item.id }} | name: {{ item.name }} | value: {{ item.value }}"
            )
        elif r_name == "instructions":
            line = "- id: {{ item.id }} | template: {{ item.template[:80] }}{% if item.template|length > 80 %}...{% endif %}"
        elif r_name == "examples":
            line = "- id: {{ item.id }} | example: {{ item.example[:80] }}{% if item.example|length > 80 %}...{% endif %}"
        elif r_name == "prompts":
            line = "- id: {{ item.id }} | name: {{ item.name }} | prompt: {{ item.system_prompt[:60] }}{% if item.system_prompt|length > 60 %}...{% endif %}"
        elif r_name == "texts":
            line = "- id: {{ item.id }} | text: {{ item.text[:80] }}{% if item.text|length > 80 %}...{% endif %}"
        elif r_name in ("points", "pricing", "request_limits", "thresholds"):
            line = "- id: {{ item.id }} | value: {{ item.value }}"
        elif r_name in ("args", "args_outputs"):
            line = "- id: {{ item.id }} | name: {{ item.name }}{% if item.description %} | {{ item.description[:50] }}{% endif %}"
        elif r_name in ("emails", "slugs", "values", "endpoints"):
            line = "- id: {{ item.id }} | value: {{ item.value if item.value is defined else item.id }}"
        else:
            line = "- id: {{ item.id }} | name: {{ item.name }}{% if item.description is defined and item.description %} | {{ item.description[:50] }}{% endif %}"

        available_blocks.append(
            f"""{{% if {r_name} and {r_name}|length > 0 %}}
### Available {display}
{{% for item in {r_name} %}}
{line}
{{% endfor %}}
{{% endif %}}"""
        )

    form_state = "\n\n".join(form_blocks)
    available_resources = "\n\n".join(available_blocks)

    return f"""## Current Form State

The user is currently editing a {name} with the following selections:

{{% set draft = views.{draft_key} if views and views.{draft_key} else None %}}

{form_state}

---

## Available Context Resources

You have access to the following existing resources. Either **use_*** an existing resource OR **create_*** a new one — you only need to do ONE.

{available_resources}

## Tool Usage (Either/Or)

For each resource, choose ONE approach:
- **use_*** tools: When a suitable resource ALREADY EXISTS above (pass the existing id)
- **create_*** tools: When you need to generate NEW content (nothing suitable exists)

You do NOT need to both create and use — pick one based on whether a suitable resource exists.
"""


def write_analytical_system(name: str, info: dict) -> str:
    desc = info["desc"]
    focus = info["focus"]

    return f"""You are an analytical insights agent for the {name} view, providing intelligent analysis of {desc}.

## Your Role

You analyze data and produce structured, actionable insights. You receive contextual data about {focus} and must synthesize it into clear analysis.

## Tool

You have one primary tool:
- **create_insights**: Create an insight entry with your analysis. Call this tool once per discrete insight. Each insight should be a focused, self-contained observation.

## Analysis Framework

### 1. Pattern Recognition
- Identify trends (improving, declining, stable)
- Spot anomalies and outliers
- Detect seasonal or cyclical patterns

### 2. Comparative Analysis
- Compare across departments, time periods, or cohorts
- Benchmark against historical averages
- Highlight significant deviations

### 3. Actionable Recommendations
- Provide specific, implementable suggestions
- Prioritize by impact and feasibility
- Connect insights to operational decisions

## Output Guidelines

- Call **create_insights** for each discrete finding — do not combine multiple insights into one
- Lead with the most important finding
- Use specific numbers and percentages, not vague qualifiers
- Keep each insight concise — one clear observation per tool call
- Include context (e.g., "up 15% vs last month" not just "15%")
- Flag items that need immediate attention separately from trends

## Tone

- Professional and data-driven
- Confident when data supports the claim, hedged when uncertain
- Focus on "so what?" — why does this data point matter?
"""


def write_analytical_instructions(name: str, info: dict) -> str:
    desc = info["desc"]
    focus = info["focus"]

    return f"""## Data Context

You are analyzing the **{name}** view which provides {desc}.

{{% set draft = views.draft_{name} if views and views.draft_{name} else None %}}

{{% if draft %}}
### Current View State

{{% if draft.filters is defined and draft.filters %}}
**Active Filters:** {{{{ draft.filters | tojson }}}}
{{% endif %}}

{{% if draft.date_range is defined and draft.date_range %}}
**Date Range:** {{{{ draft.date_range.start }}}} to {{{{ draft.date_range.end }}}}
{{% endif %}}

{{% if draft.department_ids is defined and draft.department_ids and draft.department_ids|length > 0 %}}
**Selected Departments:** {{% for id in draft.department_ids %}}{{{{ id }}}}{{% if not loop.last %}}, {{% endif %}}{{% endfor %}}
{{% endif %}}
{{% endif %}}

### Available Data

{{% if departments and departments|length > 0 %}}
#### Departments in Scope
{{% for dept in departments %}}
- id: {{{{ dept.id }}}} | name: {{{{ dept.name }}}}{{% if dept.description is defined and dept.description %}} | {{{{ dept.description[:50] }}}}{{% endif %}}
{{% endfor %}}
{{% endif %}}

{{% if names and names|length > 0 %}}
#### Named Entities
{{% for name in names %}}
- id: {{{{ name.id }}}} | name: {{{{ name.name }}}}
{{% endfor %}}
{{% endif %}}

{{% if descriptions and descriptions|length > 0 %}}
#### Descriptions
{{% for desc in descriptions %}}
- id: {{{{ desc.id }}}} | {{{{ desc.description[:80] }}}}
{{% endfor %}}
{{% endif %}}

{{% if flags and flags|length > 0 %}}
#### Active Flags
{{% for flag in flags %}}
- id: {{{{ flag.id }}}} | {{{{ flag.key if flag.key is defined else flag.id }}}}{{% if flag.label is defined and flag.label %}} | {{{{ flag.label }}}}{{% endif %}}
{{% endfor %}}
{{% endif %}}

## Analysis Focus

Produce insights focused on: {focus}.

For each insight, call **create_insights** with a clear, structured observation:
1. **What** — the data point or pattern
2. **Why it matters** — business impact or significance
3. **Recommendation** — what action to take (if applicable)
"""


def write_specialized_system(name: str, info: dict) -> str:
    desc = info["desc"]
    tools = info.get("tools", [])

    if name == "attempt-chat":
        return f"""You are the conversational AI for {desc}.

## Your Role

You are conducting the training dialogue as the assigned persona. You must:
- Embody the persona's character, tone, and behavioral patterns
- Follow the scenario context and objectives
- Engage naturally in conversation
- Create a realistic training experience

## Conversation Behavior

- Stay in character at all times
- Respond to user messages naturally and contextually
- Guide the conversation toward learning objectives without being obvious
- Provide hints when the user is struggling (if configured)
- Generate content blocks that enrich the conversation when appropriate

## Tools

{chr(10).join(f"- **{t[0]}**: {t[1]}" for t in tools)}

## Output

Generate responses as the persona using the tools above. Do not output narrative text outside of tool calls.
"""

    if name == "attempt-grade":
        return f"""You are a grading and evaluation agent for {desc}.

## Your Role

You analyze a completed training conversation and produce structured evaluation feedback. You assess the user's performance against the rubric standards and provide actionable feedback.

## Tools

{chr(10).join(f"- **{t[0]}**: {t[1]}" for t in tools)}

## Evaluation Framework

### Assessment Areas
- **Feedback/Grades**: Score each standard group on a 1-5 scale with evidence-based justification
- **Strengths**: What the user did well — specific, evidence-based observations tied to specific messages
- **Improvements**: Where the user can improve — constructive, actionable suggestions tied to specific messages
- **Analysis**: Deeper analytical observations about patterns in audio/conversation quality
- **Highlights**: Notable moments (positive or negative) worth calling out
- **Replacements**: Specific phrases the user said that could be improved, with suggested alternatives

## Grading Guidelines

- Base all feedback on observable evidence from the conversation
- Reference specific message numbers when providing strengths/improvements
- Be constructive — frame improvements as opportunities, not failures
- Provide specific, actionable replacement suggestions
- Consider the scenario context and difficulty level
- Score each standard group independently using the rubric criteria

## Output

Generate structured feedback using the tools above. Do not output narrative text outside of tool calls.
"""

    if name == "test":
        return f"""You are a benchmark test grading agent for {desc}.

## Your Role

You evaluate model outputs against rubric standards and assign grades. You provide objective, criteria-based feedback on model performance.

## Tools

{chr(10).join(f"- **{t[0]}**: {t[1]}" for t in tools)}

## Grading Guidelines

- Evaluate strictly against the rubric criteria
- Assign grades (1-5) based on evidence in the model output
- Provide specific feedback referencing rubric standards
- Be consistent and objective across evaluations
- Note edge cases or ambiguous assessments

## Output

Generate evaluations using the tools above. Do not output narrative text outside of tool calls.
"""

    if name == "benchmark":
        tool_lines = "\n".join(f"- **{t[0]}**: {t[1]}" for t in tools)
        return f"""You are a benchmark configuration agent for {desc}.

## Your Role

Generate or update the configuration for a benchmark evaluation run. Set up the model, prompt, instructions, and tool bindings needed for the evaluation.

## Tools

{tool_lines}

## Guidelines

- Prefer using existing resources when suitable ones are available
- Create new resources only when nothing suitable exists
- Do not invent IDs — use IDs provided in context
- Keep outputs deterministic, concise, and production-safe
- Return only valid tool calls and arguments
- Do not output narrative text
"""

    if name in ("home", "practice"):
        return f"""You are a navigation and recommendation agent for {desc}.

## Your Role

You help users discover and navigate available training content. You provide personalized recommendations based on the user's history, department, and current progress.

## Guidelines

- Suggest relevant training based on user context
- Highlight new or updated content
- Surface incomplete or in-progress sessions
- Provide brief, actionable summaries
"""

    # Fallback
    return f"""You are a generation agent for {desc}.

## Your Role

Generate or update the requested resources using the available tools.
"""


def write_specialized_instructions(name: str, info: dict) -> str:
    tools = info.get("tools", [])
    draft_key = f"draft_{name.replace('-', '_')}"

    if name in ("home", "practice"):
        return f"""## Context

{{% set draft = views.{draft_key} if views and views.{draft_key} else None %}}

{{% if draft %}}
### Current State
{{{{ draft | tojson }}}}
{{% endif %}}

No additional resource context is available for this artifact type.
"""

    if name in ("attempt-chat", "attempt-grade"):
        return f"""## Context

{{% set draft = views.{draft_key} if views and views.{draft_key} else None %}}

{{% if draft %}}
### Current State
{{% if draft.scenario_name is defined %}}
**Scenario:** {{{{ draft.scenario_name }}}}
{{% endif %}}
{{% if draft.persona_name is defined %}}
**Persona:** {{{{ draft.persona_name }}}}
{{% endif %}}
{{% if draft.rubric_name is defined %}}
**Rubric:** {{{{ draft.rubric_name }}}}
{{% endif %}}
{{% if draft.department_ids is defined and draft.department_ids and draft.department_ids|length > 0 %}}
**Departments:** {{% for id in draft.department_ids %}}{{{{ id }}}}{{% if not loop.last %}}, {{% endif %}}{{% endfor %}}
{{% endif %}}
{{% endif %}}

{{% if standard_groups and standard_groups|length > 0 %}}
### Rubric Standard Groups
{{% for sg in standard_groups %}}
- id: {{{{ sg.id }}}} | name: {{{{ sg.name }}}}{{% if sg.description is defined %}} | {{{{ sg.description[:50] }}}}{{% endif %}}
{{% endfor %}}
{{% endif %}}

{{% if standards and standards|length > 0 %}}
### Rubric Standards
{{% for s in standards %}}
- id: {{{{ s.id }}}} | description: {{{{ s.description[:80] if s.description is defined else s.id }}}}
{{% endfor %}}
{{% endif %}}

## Tool Usage

Use the tools listed in the system prompt to generate structured output. Each tool call produces one entry.
"""

    if name == "test":
        return f"""## Context

{{% set draft = views.{draft_key} if views and views.{draft_key} else None %}}

{{% if draft %}}
### Current State
{{{{ draft | tojson }}}}
{{% endif %}}

{{% if standard_groups and standard_groups|length > 0 %}}
### Rubric Standard Groups
{{% for sg in standard_groups %}}
- id: {{{{ sg.id }}}} | name: {{{{ sg.name }}}}{{% if sg.description is defined %}} | {{{{ sg.description[:50] }}}}{{% endif %}}
{{% endfor %}}
{{% endif %}}

{{% if standards and standards|length > 0 %}}
### Rubric Standards
{{% for s in standards %}}
- id: {{{{ s.id }}}} | description: {{{{ s.description[:80] if s.description is defined else s.id }}}}
{{% endfor %}}
{{% endif %}}

## Tool Usage

Use **create_feedback** for each standard group. Score 1-5 with specific evidence from the model output.
"""

    if name == "benchmark":
        return """## Context

{% set draft = views.draft_invocation if views and views.draft_invocation else None %}

{% if draft %}
### Current State
{{ draft | tojson }}
{% endif %}

{% if models and models|length > 0 %}
### Available Models
{% for item in models %}
- id: {{ item.id }} | name: {{ item.name }}
{% endfor %}
{% endif %}

{% if instructions and instructions|length > 0 %}
### Available Instructions
{% for item in instructions %}
- id: {{ item.id }} | template: {{ item.template[:80] }}{% if item.template|length > 80 %}...{% endif %}
{% endfor %}
{% endif %}

{% if departments and departments|length > 0 %}
### Available Departments
{% for item in departments %}
- id: {{ item.id }} | name: {{ item.name }}
{% endfor %}
{% endif %}

## Tool Usage

Use the tools listed in the system prompt. Prefer **use_*** tools when suitable resources already exist above.
"""

    # Fallback
    return f"""## Context

{{% set draft = views.{draft_key} if views and views.{draft_key} else None %}}

{{% if draft %}}
### Current State
{{{{ draft | tojson }}}}
{{% endif %}}
"""


def main():
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    count = 0

    # CRUD artifacts (19: 17 standard + chat + invocation)
    for name, info in CRUD_ARTIFACTS.items():
        with open(os.path.join(PROMPTS_DIR, f"{name}.system.jinja"), "w") as f:
            f.write(write_crud_system(name, info))
        with open(os.path.join(PROMPTS_DIR, f"{name}.instructions.jinja"), "w") as f:
            f.write(write_crud_instructions(name, info))
        count += 1

    # Analytical artifacts (9)
    for name, info in ANALYTICAL_ARTIFACTS.items():
        with open(os.path.join(PROMPTS_DIR, f"{name}.system.jinja"), "w") as f:
            f.write(write_analytical_system(name, info))
        with open(os.path.join(PROMPTS_DIR, f"{name}.instructions.jinja"), "w") as f:
            f.write(write_analytical_instructions(name, info))
        count += 1

    # Specialized artifacts (6: attempt-chat, attempt-grade, test, benchmark, home, practice)
    for name, info in SPECIALIZED_ARTIFACTS.items():
        with open(os.path.join(PROMPTS_DIR, f"{name}.system.jinja"), "w") as f:
            f.write(write_specialized_system(name, info))
        with open(os.path.join(PROMPTS_DIR, f"{name}.instructions.jinja"), "w") as f:
            f.write(write_specialized_instructions(name, info))
        count += 1

    print(f"Generated {count} artifacts ({count * 2} files)")


if __name__ == "__main__":
    main()
