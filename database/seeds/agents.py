"""Module 04 — Agent seed definitions.

Each dict maps directly to CreateAgentItem fields.
String fields (name, description) are resolved by the _impl function.
Prompts and instructions are loaded from .jinja files via prompts.py.
"""

from database.seeds.ids import sid
from database.seeds.models import ROLE_MODEL_IDS
from database.seeds.prompts import prompt_id as _prompt_id, instruction_id as _instruction_id

# ---------------------------------------------------------------------------
# Helper: role-based model assignment
# ---------------------------------------------------------------------------


def _role_model(role: str):
    mid = ROLE_MODEL_IDS.get(role)
    return mid if mid else None


# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Flags (from database/seeds/resources/flags.py)
AGENT_ACTIVE_FLAG = sid("flag/agent-active")

# Shared tools — added to every agent
GROUP_NAME_TOOL = sid("tool-resource/group/name")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules (e.g., systems.py)
# When created via _impl, artifact ID = resource ID.
# ---------------------------------------------------------------------------

ACTIVITY_AGENT = sid("agent/activity")
AGENT_AGENT = sid("agent/agent")
ATTEMPT_CHAT_AGENT = sid("agent/attempt-chat")
ATTEMPT_CHAT_AGENT_2 = sid("agent/attempt-chat-2")
ATTEMPT_GRADE_AGENT = sid("agent/attempt-grade")
AUTH_AGENT = sid("agent/auth")
BENCHMARK_AGENT = sid("agent/benchmark")
CHAT_AGENT = sid("agent/chat")
COHORT_AGENT = sid("agent/cohort")
DASHBOARD_AGENT = sid("agent/dashboard")
DEPARTMENT_AGENT = sid("agent/department")
DOCUMENT_AGENT = sid("agent/document")
EVAL_AGENT = sid("agent/eval")
FIELD_AGENT = sid("agent/field")
GROUP_AGENT = sid("agent/group")
HEALTH_AGENT = sid("agent/health")
HOME_AGENT = sid("agent/home")
INVOCATION_AGENT = sid("agent/invocation")
LEADERBOARD_AGENT = sid("agent/leaderboard")
MODEL_AGENT = sid("agent/model")
PARAMETER_AGENT = sid("agent/parameter")
PERSONA_AGENT = sid("agent/persona")
PERSONA_GEMINI_AGENT = sid("agent/persona-gemini")
PRACTICE_AGENT = sid("agent/practice")
PRICING_AGENT = sid("agent/pricing")
PROFILE_AGENT = sid("agent/profile")
PROVIDER_AGENT = sid("agent/provider")
RECORD_AGENT = sid("agent/record")
REPORTS_AGENT = sid("agent/reports")
RUBRIC_AGENT = sid("agent/rubric")
SCENARIO_AGENT = sid("agent/scenario")
SCENARIO_IMAGE_AGENT = sid("agent/scenario-image")
SCENARIO_VIDEO_AGENT = sid("agent/scenario-video")
SESSION_AGENT = sid("agent/session")
SETTING_AGENT = sid("agent/setting")
SIMULATION_AGENT = sid("agent/simulation")
TEST_GRADE_AGENT = sid("agent/test-grade")
TOOL_AGENT = sid("agent/tool")
COMPOSER_AGENT = sid("agent/composer")

# ---------------------------------------------------------------------------
# Deterministic resource IDs for agent-resource associations
# ---------------------------------------------------------------------------

ACTIVITY_AGENT_RESOURCE = sid("agent-resource/activity")
AGENT_AGENT_RESOURCE = sid("agent-resource/agent")
ATTEMPT_CHAT_AGENT_RESOURCE = sid("agent-resource/attempt-chat")
ATTEMPT_CHAT_AGENT_2_RESOURCE = sid("agent-resource/attempt-chat-2")
ATTEMPT_GRADE_AGENT_RESOURCE = sid("agent-resource/attempt-grade")
AUTH_AGENT_RESOURCE = sid("agent-resource/auth")
BENCHMARK_AGENT_RESOURCE = sid("agent-resource/benchmark")
CHAT_AGENT_RESOURCE = sid("agent-resource/chat")
COHORT_AGENT_RESOURCE = sid("agent-resource/cohort")
COMPOSER_AGENT_RESOURCE = sid("agent-resource/composer")
DASHBOARD_AGENT_RESOURCE = sid("agent-resource/dashboard")
DEPARTMENT_AGENT_RESOURCE = sid("agent-resource/department")
DOCUMENT_AGENT_RESOURCE = sid("agent-resource/document")
EVAL_AGENT_RESOURCE = sid("agent-resource/eval")
FIELD_AGENT_RESOURCE = sid("agent-resource/field")
GROUP_AGENT_RESOURCE = sid("agent-resource/group")
HEALTH_AGENT_RESOURCE = sid("agent-resource/health")
HOME_AGENT_RESOURCE = sid("agent-resource/home")
INVOCATION_AGENT_RESOURCE = sid("agent-resource/invocation")
LEADERBOARD_AGENT_RESOURCE = sid("agent-resource/leaderboard")
MODEL_AGENT_RESOURCE = sid("agent-resource/model")
PARAMETER_AGENT_RESOURCE = sid("agent-resource/parameter")
PERSONA_AGENT_RESOURCE = sid("agent-resource/persona")
PERSONA_GEMINI_AGENT_RESOURCE = sid("agent-resource/persona-gemini")
PRACTICE_AGENT_RESOURCE = sid("agent-resource/practice")
PRICING_AGENT_RESOURCE = sid("agent-resource/pricing")
PROFILE_AGENT_RESOURCE = sid("agent-resource/profile")
PROVIDER_AGENT_RESOURCE = sid("agent-resource/provider")
RECORD_AGENT_RESOURCE = sid("agent-resource/record")
REPORTS_AGENT_RESOURCE = sid("agent-resource/reports")
RUBRIC_AGENT_RESOURCE = sid("agent-resource/rubric")
SCENARIO_AGENT_RESOURCE = sid("agent-resource/scenario")
SCENARIO_IMAGE_AGENT_RESOURCE = sid("agent-resource/scenario-image")
SCENARIO_VIDEO_AGENT_RESOURCE = sid("agent-resource/scenario-video")
SESSION_AGENT_RESOURCE = sid("agent-resource/session")
SETTING_AGENT_RESOURCE = sid("agent-resource/setting")
SIMULATION_AGENT_RESOURCE = sid("agent-resource/simulation")
TEST_GRADE_AGENT_RESOURCE = sid("agent-resource/test-grade")
TOOL_AGENT_RESOURCE = sid("agent-resource/tool")

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

agents = [
    dict(
        id=ACTIVITY_AGENT,
        resource_id=ACTIVITY_AGENT_RESOURCE,
        name="Activity",
        description="Analytical insights agent for real-time activity monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/activity/export"),
            sid("tool-resource/activity/get"),
            sid("tool-resource/activity/problem"),
            sid("tool-resource/activity/refresh"),
            sid("tool-resource/activity/resolve"),
            sid("tool-resource/activity/search"),
        ],
        prompt_id=_prompt_id("Activity"),
        instruction_ids=[_instruction_id("Activity")],
    ),
    dict(
        id=AGENT_AGENT,
        resource_id=AGENT_AGENT_RESOURCE,
        name="Agent",
        description="AI agent for generating and managing agent resources including names, descriptions, flags, departments, prompts, instructions, models, and tools using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/agent/create"),
            sid("tool-resource/agent/delete"),
            sid("tool-resource/agent/draft"),
            sid("tool-resource/agent/drafts"),
            sid("tool-resource/agent/duplicate"),
            sid("tool-resource/agent/export"),
            sid("tool-resource/agent/get"),
            sid("tool-resource/agent/refresh"),
            sid("tool-resource/agent/search"),
            sid("tool-resource/agent/update"),
        ],
        prompt_id=_prompt_id("Agent"),
        instruction_ids=[_instruction_id("Agent")],
    ),
    dict(
        id=ATTEMPT_CHAT_AGENT,
        resource_id=ATTEMPT_CHAT_AGENT_RESOURCE,
        name="Attempt Chat",
        description="Conversational AI agent for conducting training dialogues as personas",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/attempt/archive"),
            sid("tool-resource/attempt/end"),
            sid("tool-resource/attempt/end-all"),
            sid("tool-resource/attempt/export"),
            sid("tool-resource/attempt/get"),
            sid("tool-resource/attempt/message"),
            sid("tool-resource/attempt/next"),
            sid("tool-resource/attempt/refresh"),
            sid("tool-resource/attempt/response"),
            sid("tool-resource/attempt/search"),
            sid("tool-resource/attempt/start"),
            sid("tool-resource/attempt/stop"),
            sid("tool-resource/attempt/use-previous"),
            sid("tool-resource/attempt-audio/create"),
            sid("tool-resource/attempt-audio/download"),
            sid("tool-resource/attempt-audio/start"),
            sid("tool-resource/attempt-audio/frame"),
            sid("tool-resource/attempt-audio/stop"),
            sid("tool-resource/attempt-audio/mute"),
        ],
        prompt_id=_prompt_id("Attempt Chat"),
        instruction_ids=[_instruction_id("Attempt Chat")],
    ),
    dict(
        id=ATTEMPT_GRADE_AGENT,
        resource_id=ATTEMPT_GRADE_AGENT_RESOURCE,
        name="Attempt Grade",
        description="Grading and evaluation agent for analyzing training attempt performance",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("grader"),
        tool_ids=[
            sid("tool-resource/attempt/grade"),
        ],
        prompt_id=_prompt_id("Attempt Grade"),
        instruction_ids=[_instruction_id("Attempt Grade")],
    ),
    dict(
        id=AUTH_AGENT,
        resource_id=AUTH_AGENT_RESOURCE,
        name="Auth",
        description="AI agent for generating and managing auth resources including names, descriptions, flags, protocols, slugs, and items using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/auth/create"),
            sid("tool-resource/auth/delete"),
            sid("tool-resource/auth/draft"),
            sid("tool-resource/auth/drafts"),
            sid("tool-resource/auth/duplicate"),
            sid("tool-resource/auth/export"),
            sid("tool-resource/auth/get"),
            sid("tool-resource/auth/refresh"),
            sid("tool-resource/auth/search"),
            sid("tool-resource/auth/update"),
        ],
        prompt_id=_prompt_id("Auth"),
        instruction_ids=[_instruction_id("Auth")],
    ),
    dict(
        id=BENCHMARK_AGENT,
        resource_id=BENCHMARK_AGENT_RESOURCE,
        name="Benchmark",
        description="AI agent for generating analytical insights about benchmark evaluation results including cross-model performance and scoring quality",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/benchmark/export"),
            sid("tool-resource/benchmark/get"),
            sid("tool-resource/benchmark/refresh"),
            sid("tool-resource/benchmark/search"),
        ],
        prompt_id=_prompt_id("Benchmark"),
        instruction_ids=[_instruction_id("Benchmark")],
    ),
    dict(
        id=CHAT_AGENT,
        resource_id=CHAT_AGENT_RESOURCE,
        name="Chat",
        description="AI agent for creating and managing training chat sessions with persona-driven scenario conversations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/chat/draft"),
            sid("tool-resource/chat/drafts"),
            sid("tool-resource/chat/export"),
            sid("tool-resource/chat/get"),
            sid("tool-resource/chat/refresh"),
        ],
        prompt_id=_prompt_id("Chat"),
        instruction_ids=[_instruction_id("Chat")],
    ),
    dict(
        id=COHORT_AGENT,
        resource_id=COHORT_AGENT_RESOURCE,
        name="Cohort",
        description="AI agent for generating and managing cohort resources including names, descriptions, flags, departments, personas, and scenarios using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/cohort/create"),
            sid("tool-resource/cohort/delete"),
            sid("tool-resource/cohort/draft"),
            sid("tool-resource/cohort/drafts"),
            sid("tool-resource/cohort/duplicate"),
            sid("tool-resource/cohort/export"),
            sid("tool-resource/cohort/get"),
            sid("tool-resource/cohort/refresh"),
            sid("tool-resource/cohort/search"),
            sid("tool-resource/cohort/update"),
        ],
        prompt_id=_prompt_id("Cohort"),
        instruction_ids=[_instruction_id("Cohort")],
    ),
    dict(
        id=DASHBOARD_AGENT,
        resource_id=DASHBOARD_AGENT_RESOURCE,
        name="Dashboard",
        description="Analytical insights agent for high-level organizational KPIs and trends",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/dashboard/export"),
            sid("tool-resource/dashboard/get"),
            sid("tool-resource/dashboard/refresh"),
            sid("tool-resource/dashboard/search"),
        ],
        prompt_id=_prompt_id("Dashboard"),
        instruction_ids=[_instruction_id("Dashboard")],
    ),
    dict(
        id=DEPARTMENT_AGENT,
        resource_id=DEPARTMENT_AGENT_RESOURCE,
        name="Department",
        description="AI agent for generating and managing department resources including names, descriptions, flags, and settings using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/department/create"),
            sid("tool-resource/department/delete"),
            sid("tool-resource/department/draft"),
            sid("tool-resource/department/drafts"),
            sid("tool-resource/department/duplicate"),
            sid("tool-resource/department/export"),
            sid("tool-resource/department/get"),
            sid("tool-resource/department/refresh"),
            sid("tool-resource/department/search"),
            sid("tool-resource/department/update"),
        ],
        prompt_id=_prompt_id("Department"),
        instruction_ids=[_instruction_id("Department")],
    ),
    dict(
        id=DOCUMENT_AGENT,
        resource_id=DOCUMENT_AGENT_RESOURCE,
        name="Document",
        description="Agent for generating and working with documents, templates, and structured content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/document/create"),
            sid("tool-resource/document/delete"),
            sid("tool-resource/document/draft"),
            sid("tool-resource/document/drafts"),
            sid("tool-resource/document/duplicate"),
            sid("tool-resource/document/export"),
            sid("tool-resource/document/get"),
            sid("tool-resource/document/refresh"),
            sid("tool-resource/document/search"),
            sid("tool-resource/document/update"),
            sid("tool-resource/document-text/create"),
            sid("tool-resource/document-text/download"),
            sid("tool-resource/document-file/create"),
            sid("tool-resource/document-file/download"),
            sid("tool-resource/document-file/preview"),
        ],
        prompt_id=_prompt_id("Document"),
        instruction_ids=[_instruction_id("Document")],
    ),
    dict(
        id=EVAL_AGENT,
        resource_id=EVAL_AGENT_RESOURCE,
        name="Eval",
        description="AI agent for generating and managing eval resources including names, descriptions, flags, departments, scenarios, rubrics, and various eval-specific resources using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/eval/create"),
            sid("tool-resource/eval/delete"),
            sid("tool-resource/eval/draft"),
            sid("tool-resource/eval/drafts"),
            sid("tool-resource/eval/duplicate"),
            sid("tool-resource/eval/export"),
            sid("tool-resource/eval/get"),
            sid("tool-resource/eval/refresh"),
            sid("tool-resource/eval/search"),
            sid("tool-resource/eval/update"),
        ],
        prompt_id=_prompt_id("Eval"),
        instruction_ids=[_instruction_id("Eval")],
    ),
    dict(
        id=FIELD_AGENT,
        resource_id=FIELD_AGENT_RESOURCE,
        name="Field",
        description="AI agent for generating and managing field resources including names, descriptions, flags, departments, and conditional parameters using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/field/create"),
            sid("tool-resource/field/delete"),
            sid("tool-resource/field/draft"),
            sid("tool-resource/field/drafts"),
            sid("tool-resource/field/duplicate"),
            sid("tool-resource/field/export"),
            sid("tool-resource/field/get"),
            sid("tool-resource/field/refresh"),
            sid("tool-resource/field/search"),
            sid("tool-resource/field/update"),
        ],
        prompt_id=_prompt_id("Field"),
        instruction_ids=[_instruction_id("Field")],
    ),
    dict(
        id=GROUP_AGENT,
        resource_id=GROUP_AGENT_RESOURCE,
        name="Group",
        description="Analytical insights agent for group-level analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/group/export"),
            sid("tool-resource/group/generate"),
            sid("tool-resource/group/get"),
            sid("tool-resource/group/name"),
            sid("tool-resource/group/refresh"),
            sid("tool-resource/group/search"),
        ],
        prompt_id=_prompt_id("Group"),
        instruction_ids=[_instruction_id("Group")],
    ),
    dict(
        id=HEALTH_AGENT,
        resource_id=HEALTH_AGENT_RESOURCE,
        name="Health",
        description="Analytical insights agent for system health monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/health/export"),
            sid("tool-resource/health/get"),
            sid("tool-resource/health/refresh"),
        ],
        prompt_id=_prompt_id("Health"),
        instruction_ids=[_instruction_id("Health")],
    ),
    dict(
        id=HOME_AGENT,
        resource_id=HOME_AGENT_RESOURCE,
        name="Home",
        description="Navigation and recommendation agent for home page overview",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/home/export"),
            sid("tool-resource/home/get"),
            sid("tool-resource/home/refresh"),
            sid("tool-resource/home/search"),
        ],
        prompt_id=_prompt_id("Home"),
        instruction_ids=[_instruction_id("Home")],
    ),
    dict(
        id=INVOCATION_AGENT,
        resource_id=INVOCATION_AGENT_RESOURCE,
        name="Invocation",
        description="AI agent for creating and managing benchmark invocations with model and tool configurations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/invocation/decrypt"),
            sid("tool-resource/invocation/draft"),
            sid("tool-resource/invocation/drafts"),
            sid("tool-resource/invocation/export"),
            sid("tool-resource/invocation/get"),
            sid("tool-resource/invocation/refresh"),
        ],
        prompt_id=_prompt_id("Invocation"),
        instruction_ids=[_instruction_id("Invocation")],
    ),
    dict(
        id=LEADERBOARD_AGENT,
        resource_id=LEADERBOARD_AGENT_RESOURCE,
        name="Leaderboard",
        description="Analytical insights agent for performance rankings",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/leaderboard/export"),
            sid("tool-resource/leaderboard/get"),
            sid("tool-resource/leaderboard/refresh"),
            sid("tool-resource/leaderboard/search"),
        ],
        prompt_id=_prompt_id("Leaderboard"),
        instruction_ids=[_instruction_id("Leaderboard")],
    ),
    dict(
        id=MODEL_AGENT,
        resource_id=MODEL_AGENT_RESOURCE,
        name="Model",
        description="AI agent for generating and managing model resources including names, descriptions, flags, departments, endpoints, keys, modalities, and providers using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/model/create"),
            sid("tool-resource/model/delete"),
            sid("tool-resource/model/draft"),
            sid("tool-resource/model/drafts"),
            sid("tool-resource/model/duplicate"),
            sid("tool-resource/model/export"),
            sid("tool-resource/model/get"),
            sid("tool-resource/model/refresh"),
            sid("tool-resource/model/search"),
            sid("tool-resource/model/update"),
        ],
        prompt_id=_prompt_id("Model"),
        instruction_ids=[_instruction_id("Model")],
    ),
    dict(
        id=PARAMETER_AGENT,
        resource_id=PARAMETER_AGENT_RESOURCE,
        name="Parameter",
        description="AI agent for generating and managing parameter resources including names, descriptions, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/parameter/create"),
            sid("tool-resource/parameter/delete"),
            sid("tool-resource/parameter/draft"),
            sid("tool-resource/parameter/drafts"),
            sid("tool-resource/parameter/duplicate"),
            sid("tool-resource/parameter/export"),
            sid("tool-resource/parameter/get"),
            sid("tool-resource/parameter/refresh"),
            sid("tool-resource/parameter/search"),
            sid("tool-resource/parameter/update"),
        ],
        prompt_id=_prompt_id("Parameter"),
        instruction_ids=[_instruction_id("Parameter")],
    ),
    dict(
        id=PERSONA_AGENT,
        resource_id=PERSONA_AGENT_RESOURCE,
        name="Persona",
        description="AI agent for generating and managing persona resources including names, descriptions, colors, icons, instructions, examples, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/persona/create"),
            sid("tool-resource/persona/csv"),
            sid("tool-resource/persona/delete"),
            sid("tool-resource/persona/docs"),
            sid("tool-resource/persona/draft"),
            sid("tool-resource/persona/drafts"),
            sid("tool-resource/persona/duplicate"),
            sid("tool-resource/persona/export"),
            sid("tool-resource/persona/generate"),
            sid("tool-resource/persona/generations"),
            sid("tool-resource/persona/get"),
            sid("tool-resource/persona/group"),
            sid("tool-resource/persona/problem"),
            sid("tool-resource/persona/refresh"),
            sid("tool-resource/persona/search"),
            sid("tool-resource/persona/update"),
        ],
        rubric_ids=[sid("rubric-resource/persona-rubric")],
        prompt_id=_prompt_id("Persona"),
        instruction_ids=[_instruction_id("Persona")],
    ),
    dict(
        id=PERSONA_GEMINI_AGENT,
        resource_id=PERSONA_GEMINI_AGENT_RESOURCE,
        name="Persona Gemini",
        description="AI agent for generating and managing persona resources using Gemini 2.5 Flash",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=sid("model-resource/gemini-2.5-flash"),
        tool_ids=[
            sid("tool-resource/persona/create"),
            sid("tool-resource/persona/csv"),
            sid("tool-resource/persona/delete"),
            sid("tool-resource/persona/docs"),
            sid("tool-resource/persona/draft"),
            sid("tool-resource/persona/drafts"),
            sid("tool-resource/persona/duplicate"),
            sid("tool-resource/persona/export"),
            sid("tool-resource/persona/generate"),
            sid("tool-resource/persona/generations"),
            sid("tool-resource/persona/get"),
            sid("tool-resource/persona/group"),
            sid("tool-resource/persona/problem"),
            sid("tool-resource/persona/refresh"),
            sid("tool-resource/persona/search"),
            sid("tool-resource/persona/update"),
        ],
        rubric_ids=[sid("rubric-resource/persona-rubric")],
        prompt_id=_prompt_id("Persona"),
        instruction_ids=[_instruction_id("Persona")],
    ),
    dict(
        id=PRACTICE_AGENT,
        resource_id=PRACTICE_AGENT_RESOURCE,
        name="Practice",
        description="Navigation and recommendation agent for practice mode entry point",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/practice/export"),
            sid("tool-resource/practice/get"),
            sid("tool-resource/practice/refresh"),
            sid("tool-resource/practice/search"),
        ],
        prompt_id=_prompt_id("Practice"),
        instruction_ids=[_instruction_id("Practice")],
    ),
    dict(
        id=PRICING_AGENT,
        resource_id=PRICING_AGENT_RESOURCE,
        name="Pricing",
        description="Analytical insights agent for cost analytics and billing breakdowns",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/pricing/export"),
            sid("tool-resource/pricing/get"),
            sid("tool-resource/pricing/refresh"),
            sid("tool-resource/pricing/search"),
        ],
        prompt_id=_prompt_id("Pricing"),
        instruction_ids=[_instruction_id("Pricing")],
    ),
    dict(
        id=PROFILE_AGENT,
        resource_id=PROFILE_AGENT_RESOURCE,
        name="Profile",
        description="AI agent for generating and managing profile resources including names, descriptions, flags, departments, emails, cohorts, and request limits using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/profile/context"),
            sid("tool-resource/profile/create"),
            sid("tool-resource/profile/delete"),
            sid("tool-resource/profile/draft"),
            sid("tool-resource/profile/drafts"),
            sid("tool-resource/profile/duplicate"),
            sid("tool-resource/profile/emulate"),
            sid("tool-resource/profile/export"),
            sid("tool-resource/profile/get"),
            sid("tool-resource/profile/refresh"),
            sid("tool-resource/profile/search"),
            sid("tool-resource/profile/unemulate"),
            sid("tool-resource/profile/update"),
        ],
        prompt_id=_prompt_id("Profile"),
        instruction_ids=[_instruction_id("Profile")],
    ),
    dict(
        id=PROVIDER_AGENT,
        resource_id=PROVIDER_AGENT_RESOURCE,
        name="Provider",
        description="AI agent for generating and managing provider resources including names, descriptions, flags, and endpoints using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/provider/create"),
            sid("tool-resource/provider/decrypt"),
            sid("tool-resource/provider/delete"),
            sid("tool-resource/provider/draft"),
            sid("tool-resource/provider/drafts"),
            sid("tool-resource/provider/duplicate"),
            sid("tool-resource/provider/export"),
            sid("tool-resource/provider/get"),
            sid("tool-resource/provider/refresh"),
            sid("tool-resource/provider/search"),
            sid("tool-resource/provider/update"),
        ],
        prompt_id=_prompt_id("Provider"),
        instruction_ids=[_instruction_id("Provider")],
    ),
    dict(
        id=RECORD_AGENT,
        resource_id=RECORD_AGENT_RESOURCE,
        name="Record",
        description="Analytical insights agent for individual training record analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/record/export"),
            sid("tool-resource/record/get"),
            sid("tool-resource/record/refresh"),
            sid("tool-resource/record/search"),
        ],
        prompt_id=_prompt_id("Record"),
        instruction_ids=[_instruction_id("Record")],
    ),
    dict(
        id=REPORTS_AGENT,
        resource_id=REPORTS_AGENT_RESOURCE,
        name="Reports",
        description="Analytical insights agent for detailed training outcome reports",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/reports/export"),
            sid("tool-resource/reports/get"),
            sid("tool-resource/reports/refresh"),
            sid("tool-resource/reports/search"),
        ],
        prompt_id=_prompt_id("Reports"),
        instruction_ids=[_instruction_id("Reports")],
    ),
    dict(
        id=RUBRIC_AGENT,
        resource_id=RUBRIC_AGENT_RESOURCE,
        name="Rubric",
        description="Agent for generating rubric descriptions and grid cell content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/rubric/create"),
            sid("tool-resource/rubric/delete"),
            sid("tool-resource/rubric/draft"),
            sid("tool-resource/rubric/drafts"),
            sid("tool-resource/rubric/duplicate"),
            sid("tool-resource/rubric/export"),
            sid("tool-resource/rubric/get"),
            sid("tool-resource/rubric/refresh"),
            sid("tool-resource/rubric/search"),
            sid("tool-resource/rubric/update"),
        ],
        prompt_id=_prompt_id("Rubric"),
        instruction_ids=[_instruction_id("Rubric")],
    ),
    dict(
        id=SCENARIO_AGENT,
        resource_id=SCENARIO_AGENT_RESOURCE,
        name="Scenario",
        description="Helps create distinct scenarios for chat interactions.",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/scenario/create"),
            sid("tool-resource/scenario/delete"),
            sid("tool-resource/scenario/draft"),
            sid("tool-resource/scenario/drafts"),
            sid("tool-resource/scenario/duplicate"),
            sid("tool-resource/scenario/export"),
            sid("tool-resource/scenario/generate"),
            sid("tool-resource/scenario/generations"),
            sid("tool-resource/scenario/get"),
            sid("tool-resource/scenario/group"),
            sid("tool-resource/scenario/problem"),
            sid("tool-resource/scenario/refresh"),
            sid("tool-resource/scenario/search"),
            sid("tool-resource/scenario/update"),
            sid("tool-resource/scenario-image/create"),
            sid("tool-resource/scenario-image/download"),
            sid("tool-resource/scenario-video/create"),
            sid("tool-resource/scenario-video/download"),
        ],
        prompt_id=_prompt_id("Scenario"),
        instruction_ids=[_instruction_id("Scenario")],
    ),
    dict(
        id=SCENARIO_IMAGE_AGENT,
        resource_id=SCENARIO_IMAGE_AGENT_RESOURCE,
        name="Scenario Image",
        description="Image generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("image"),
        tool_ids=[
            sid("tool-resource/scenario-image/create"),
        ],
    ),
    dict(
        id=SCENARIO_VIDEO_AGENT,
        resource_id=SCENARIO_VIDEO_AGENT_RESOURCE,
        name="Scenario Video",
        description="Video generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("video"),
        tool_ids=[
            sid("tool-resource/scenario-video/create"),
        ],
    ),
    dict(
        id=SESSION_AGENT,
        resource_id=SESSION_AGENT_RESOURCE,
        name="Session",
        description="Analytical insights agent for individual training session analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/session/export"),
            sid("tool-resource/session/get"),
            sid("tool-resource/session/refresh"),
        ],
        prompt_id=_prompt_id("Session"),
        instruction_ids=[_instruction_id("Session")],
    ),
    dict(
        id=SETTING_AGENT,
        resource_id=SETTING_AGENT_RESOURCE,
        name="Setting",
        description="AI agent for generating and managing setting resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/setting/create"),
            sid("tool-resource/setting/decrypt"),
            sid("tool-resource/setting/delete"),
            sid("tool-resource/setting/draft"),
            sid("tool-resource/setting/drafts"),
            sid("tool-resource/setting/duplicate"),
            sid("tool-resource/setting/export"),
            sid("tool-resource/setting/get"),
            sid("tool-resource/setting/refresh"),
            sid("tool-resource/setting/search"),
            sid("tool-resource/setting/update"),
        ],
        prompt_id=_prompt_id("Setting"),
        instruction_ids=[_instruction_id("Setting")],
    ),
    dict(
        id=SIMULATION_AGENT,
        resource_id=SIMULATION_AGENT_RESOURCE,
        name="Simulation",
        description="AI agent for generating and managing simulation scenario resources including scenarios, scenario positions, scenario flags, and scenario rubric grade agents",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/simulation/create"),
            sid("tool-resource/simulation/delete"),
            sid("tool-resource/simulation/draft"),
            sid("tool-resource/simulation/drafts"),
            sid("tool-resource/simulation/duplicate"),
            sid("tool-resource/simulation/export"),
            sid("tool-resource/simulation/get"),
            sid("tool-resource/simulation/refresh"),
            sid("tool-resource/simulation/search"),
            sid("tool-resource/simulation/update"),
        ],
        prompt_id=_prompt_id("Simulation"),
        instruction_ids=[_instruction_id("Simulation")],
    ),
    dict(
        id=TEST_GRADE_AGENT,
        resource_id=TEST_GRADE_AGENT_RESOURCE,
        name="Test Grade",
        description="Benchmark test grading agent for evaluating model outputs against rubric standards",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("grader"),
        tool_ids=[
            sid("tool-resource/test/archive"),
            sid("tool-resource/test/end"),
            sid("tool-resource/test/export"),
            sid("tool-resource/test/get"),
            sid("tool-resource/test/next"),
            sid("tool-resource/test/refresh"),
            sid("tool-resource/test/run"),
            sid("tool-resource/test/search"),
            sid("tool-resource/test/start"),
            sid("tool-resource/test/stop"),
            sid("tool-resource/test/grade"),
            sid("tool-resource/test/feedback"),
            sid("tool-resource/test/text-download"),
            sid("tool-resource/test/call-download"),
        ],
        prompt_id=_prompt_id("Test Grade"),
        instruction_ids=[_instruction_id("Test Grade")],
    ),
    dict(
        id=TOOL_AGENT,
        resource_id=TOOL_AGENT_RESOURCE,
        name="Tool",
        description="AI agent for generating and managing tool resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/tool/create"),
            sid("tool-resource/tool/delete"),
            sid("tool-resource/tool/draft"),
            sid("tool-resource/tool/drafts"),
            sid("tool-resource/tool/duplicate"),
            sid("tool-resource/tool/export"),
            sid("tool-resource/tool/get"),
            sid("tool-resource/tool/refresh"),
            sid("tool-resource/tool/search"),
            sid("tool-resource/tool/update"),
        ],
        prompt_id=_prompt_id("Tool"),
        instruction_ids=[_instruction_id("Tool")],
    ),
    dict(
        id=COMPOSER_AGENT,
        resource_id=COMPOSER_AGENT_RESOURCE,
        name="Composer",
        description="General-purpose orchestration agent for cross-cutting content, deployment, and infrastructure operations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_id=_role_model("text"),
        tool_ids=[
            sid("tool-resource/create/content"),
            sid("tool-resource/create/deployment"),
            sid("tool-resource/create/infrastructure"),
            sid("tool-resource/delete/content"),
            sid("tool-resource/delete/deployment"),
            sid("tool-resource/delete/infrastructure"),
            sid("tool-resource/duplicate/content"),
            sid("tool-resource/duplicate/deployment"),
            sid("tool-resource/duplicate/infrastructure"),
            sid("tool-resource/manage/attempt"),
            sid("tool-resource/run/attempt"),
            sid("tool-resource/run/test"),
            sid("tool-resource/search/content"),
            sid("tool-resource/search/deployment"),
            sid("tool-resource/search/infrastructure"),
            sid("tool-resource/update/content"),
            sid("tool-resource/update/deployment"),
            sid("tool-resource/update/infrastructure"),
            sid("tool-resource/view/dashboards"),
        ],
    ),
]

# Add shared tools to every agent
for _agent in agents:
    if GROUP_NAME_TOOL not in _agent["tool_ids"]:
        _agent["tool_ids"].append(GROUP_NAME_TOOL)
