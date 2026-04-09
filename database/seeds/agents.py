"""Module 04 — Agent seed definitions.

Each dict maps directly to CreateAgentItem fields.
String fields (name, description) are resolved by the _impl function.

Note: Agent prompts and instructions are NOT included here — the
CreateAgentItem / create_agent_impl does not support prompt/instruction
junctions. These must be added separately after initial creation.
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.models import ROLE_MODEL_IDS

# ---------------------------------------------------------------------------
# Helper: role-based model assignment
# ---------------------------------------------------------------------------


def _role_model(role: str) -> list:
    mid = ROLE_MODEL_IDS.get(role)
    return [mid] if mid else []


# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Flags (from database/seeds/resources/flags.py)
AGENT_ACTIVE_FLAG = UUID("019be334-bfc4-76ac-80d3-c8ba7618bc7a")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules (e.g., systems.py)
# When created via _impl, artifact ID = resource ID.
# ---------------------------------------------------------------------------

ACTIVITY_AGENT = UUID("ab00000a-0000-0000-0000-00000000000a")
AGENT_AGENT = UUID("88888888-8888-8888-8888-888888888888")
ATTEMPT_CHAT_AGENT = UUID("ab000002-0000-0000-0000-000000000002")
ATTEMPT_CHAT_AGENT_2 = UUID("019c82b8-5d9a-7b9e-92f2-278f3c55d7aa")
ATTEMPT_GRADE_AGENT = UUID("ab000003-0000-0000-0000-000000000003")
AUTH_AGENT = UUID("22222222-2222-2222-2222-222222222222")
BENCHMARK_AGENT = UUID("aabbccdd-aabb-ccdd-aabb-ccddaabbccdd")
CHAT_AGENT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
COHORT_AGENT = UUID("66666666-6666-6666-6666-666666666666")
DASHBOARD_AGENT = UUID("ab000007-0000-0000-0000-000000000007")
DEPARTMENT_AGENT = UUID("44444444-4444-4444-4444-444444444444")
DOCUMENT_AGENT = UUID("019b3be4-3112-774d-82b2-c4c3ed98238e")
EVAL_AGENT = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
FIELD_AGENT = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
GROUP_AGENT = UUID("ab00000f-0000-0000-0000-00000000000f")
HEALTH_AGENT = UUID("ab00000d-0000-0000-0000-00000000000d")
HOME_AGENT = UUID("ab000005-0000-0000-0000-000000000005")
INVOCATION_AGENT = UUID("ab000001-0000-0000-0000-000000000001")
LEADERBOARD_AGENT = UUID("ab00000e-0000-0000-0000-00000000000e")
MODEL_AGENT = UUID("99999999-9999-9999-9999-999999999999")
PARAMETER_AGENT = UUID("11111111-1111-1111-1111-111111111111")
PERSONA_AGENT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PRACTICE_AGENT = UUID("ab000006-0000-0000-0000-000000000006")
PRICING_AGENT = UUID("ab00000c-0000-0000-0000-00000000000c")
PROFILE_AGENT = UUID("33333333-3333-3333-3333-333333333333")
PROVIDER_AGENT = UUID("00000000-0000-0000-0000-000000000000")
RECORD_AGENT = UUID("ab000009-0000-0000-0000-000000000009")
REPORTS_AGENT = UUID("ab000008-0000-0000-0000-000000000008")
RUBRIC_AGENT = UUID("019b3be4-3112-7786-ad7d-45ee39b86bc5")
SCENARIO_AGENT = UUID("019b3be4-3112-7685-8967-a5488fadb090")
SCENARIO_IMAGE_AGENT = UUID("f6533535-6087-4e6d-9fd3-ed92cc9c1021")
SCENARIO_VIDEO_AGENT = UUID("3937bcae-527f-495f-82c5-476d18ce7fed")
SESSION_AGENT = UUID("ab00000b-0000-0000-0000-00000000000b")
SETTING_AGENT = UUID("77777777-7777-7777-7777-777777777777")
SIMULATION_AGENT = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
TEST_GRADE_AGENT = UUID("ab000004-0000-0000-0000-000000000004")
TOOL_AGENT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COMPOSER_AGENT = UUID("ab000010-0000-0000-0000-000000000010")

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

agents = [
    dict(
        id=ACTIVITY_AGENT,
        name="Activity",
        description="Analytical insights agent for real-time activity monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/activity/export"),
            sid("tool-resource/activity/get"),
            sid("tool-resource/activity/problem"),
            sid("tool-resource/activity/refresh"),
            sid("tool-resource/activity/resolve"),
            sid("tool-resource/activity/search"),
        ],
    ),
    dict(
        id=AGENT_AGENT,
        name="Agent",
        description="AI agent for generating and managing agent resources including names, descriptions, flags, departments, prompts, instructions, models, and tools using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=ATTEMPT_CHAT_AGENT,
        name="Attempt Chat",
        description="Conversational AI agent for conducting training dialogues as personas",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=ATTEMPT_GRADE_AGENT,
        name="Attempt Grade",
        description="Grading and evaluation agent for analyzing training attempt performance",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("grader"),
        tool_ids=[
            sid("tool-resource/attempt/grade"),
        ],
    ),
    dict(
        id=AUTH_AGENT,
        name="Auth",
        description="AI agent for generating and managing auth resources including names, descriptions, flags, protocols, slugs, and items using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=BENCHMARK_AGENT,
        name="Benchmark",
        description="AI agent for generating analytical insights about benchmark evaluation results including cross-model performance and scoring quality",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/benchmark/export"),
            sid("tool-resource/benchmark/get"),
            sid("tool-resource/benchmark/refresh"),
            sid("tool-resource/benchmark/search"),
        ],
    ),
    dict(
        id=CHAT_AGENT,
        name="Chat",
        description="AI agent for creating and managing training chat sessions with persona-driven scenario conversations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/chat/draft"),
            sid("tool-resource/chat/drafts"),
            sid("tool-resource/chat/export"),
            sid("tool-resource/chat/get"),
            sid("tool-resource/chat/refresh"),
        ],
    ),
    dict(
        id=COHORT_AGENT,
        name="Cohort",
        description="AI agent for generating and managing cohort resources including names, descriptions, flags, departments, personas, and scenarios using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=DASHBOARD_AGENT,
        name="Dashboard",
        description="Analytical insights agent for high-level organizational KPIs and trends",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/dashboard/export"),
            sid("tool-resource/dashboard/get"),
            sid("tool-resource/dashboard/refresh"),
            sid("tool-resource/dashboard/search"),
        ],
    ),
    dict(
        id=DEPARTMENT_AGENT,
        name="Department",
        description="AI agent for generating and managing department resources including names, descriptions, flags, and settings using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=DOCUMENT_AGENT,
        name="Document",
        description="Agent for generating and working with documents, templates, and structured content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=EVAL_AGENT,
        name="Eval",
        description="AI agent for generating and managing eval resources including names, descriptions, flags, departments, scenarios, rubrics, and various eval-specific resources using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=FIELD_AGENT,
        name="Field",
        description="AI agent for generating and managing field resources including names, descriptions, flags, departments, and conditional parameters using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=GROUP_AGENT,
        name="Group",
        description="Analytical insights agent for group-level analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/group/export"),
            sid("tool-resource/group/generate"),
            sid("tool-resource/group/get"),
            sid("tool-resource/group/refresh"),
        ],
    ),
    dict(
        id=HEALTH_AGENT,
        name="Health",
        description="Analytical insights agent for system health monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/health/export"),
            sid("tool-resource/health/get"),
            sid("tool-resource/health/refresh"),
        ],
    ),
    dict(
        id=HOME_AGENT,
        name="Home",
        description="Navigation and recommendation agent for home page overview",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/home/export"),
            sid("tool-resource/home/get"),
            sid("tool-resource/home/refresh"),
            sid("tool-resource/home/search"),
        ],
    ),
    dict(
        id=INVOCATION_AGENT,
        name="Invocation",
        description="AI agent for creating and managing benchmark invocations with model and tool configurations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/invocation/decrypt"),
            sid("tool-resource/invocation/draft"),
            sid("tool-resource/invocation/drafts"),
            sid("tool-resource/invocation/export"),
            sid("tool-resource/invocation/get"),
            sid("tool-resource/invocation/refresh"),
        ],
    ),
    dict(
        id=LEADERBOARD_AGENT,
        name="Leaderboard",
        description="Analytical insights agent for performance rankings",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/leaderboard/export"),
            sid("tool-resource/leaderboard/get"),
            sid("tool-resource/leaderboard/refresh"),
            sid("tool-resource/leaderboard/search"),
        ],
    ),
    dict(
        id=MODEL_AGENT,
        name="Model",
        description="AI agent for generating and managing model resources including names, descriptions, flags, departments, endpoints, keys, modalities, and providers using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=PARAMETER_AGENT,
        name="Parameter",
        description="AI agent for generating and managing parameter resources including names, descriptions, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=PERSONA_AGENT,
        name="Persona",
        description="AI agent for generating and managing persona resources including names, descriptions, colors, icons, instructions, examples, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/persona/create"),
            sid("tool-resource/persona/delete"),
            sid("tool-resource/persona/draft"),
            sid("tool-resource/persona/drafts"),
            sid("tool-resource/persona/duplicate"),
            sid("tool-resource/persona/export"),
            sid("tool-resource/persona/get"),
            sid("tool-resource/persona/refresh"),
            sid("tool-resource/persona/search"),
            sid("tool-resource/persona/update"),
        ],
    ),
    dict(
        id=PRACTICE_AGENT,
        name="Practice",
        description="Navigation and recommendation agent for practice mode entry point",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/practice/export"),
            sid("tool-resource/practice/get"),
            sid("tool-resource/practice/refresh"),
            sid("tool-resource/practice/search"),
        ],
    ),
    dict(
        id=PRICING_AGENT,
        name="Pricing",
        description="Analytical insights agent for cost analytics and billing breakdowns",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/pricing/export"),
            sid("tool-resource/pricing/get"),
            sid("tool-resource/pricing/refresh"),
            sid("tool-resource/pricing/search"),
        ],
    ),
    dict(
        id=PROFILE_AGENT,
        name="Profile",
        description="AI agent for generating and managing profile resources including names, descriptions, flags, departments, emails, cohorts, and request limits using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=PROVIDER_AGENT,
        name="Provider",
        description="AI agent for generating and managing provider resources including names, descriptions, flags, and endpoints using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=RECORD_AGENT,
        name="Record",
        description="Analytical insights agent for individual training record analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/record/export"),
            sid("tool-resource/record/get"),
            sid("tool-resource/record/refresh"),
            sid("tool-resource/record/search"),
        ],
    ),
    dict(
        id=REPORTS_AGENT,
        name="Reports",
        description="Analytical insights agent for detailed training outcome reports",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/reports/export"),
            sid("tool-resource/reports/get"),
            sid("tool-resource/reports/refresh"),
            sid("tool-resource/reports/search"),
        ],
    ),
    dict(
        id=RUBRIC_AGENT,
        name="Rubric",
        description="Agent for generating rubric descriptions and grid cell content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=SCENARIO_AGENT,
        name="Scenario",
        description="Helps create distinct scenarios for chat interactions.",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/scenario/create"),
            sid("tool-resource/scenario/delete"),
            sid("tool-resource/scenario/draft"),
            sid("tool-resource/scenario/drafts"),
            sid("tool-resource/scenario/duplicate"),
            sid("tool-resource/scenario/export"),
            sid("tool-resource/scenario/get"),
            sid("tool-resource/scenario/refresh"),
            sid("tool-resource/scenario/search"),
            sid("tool-resource/scenario/update"),
        ],
    ),
    dict(
        id=SCENARIO_IMAGE_AGENT,
        name="Scenario Image",
        description="Image generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("image"),
        tool_ids=[
            sid("tool-resource/scenario-image/create"),
            sid("tool-resource/scenario-image/download"),
        ],
    ),
    dict(
        id=SCENARIO_VIDEO_AGENT,
        name="Scenario Video",
        description="Video generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("video"),
        tool_ids=[
            sid("tool-resource/scenario-video/create"),
            sid("tool-resource/scenario-video/download"),
        ],
    ),
    dict(
        id=SESSION_AGENT,
        name="Session",
        description="Analytical insights agent for individual training session analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
        tool_ids=[
            sid("tool-resource/session/export"),
            sid("tool-resource/session/get"),
            sid("tool-resource/session/refresh"),
        ],
    ),
    dict(
        id=SETTING_AGENT,
        name="Setting",
        description="AI agent for generating and managing setting resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=SIMULATION_AGENT,
        name="Simulation",
        description="AI agent for generating and managing simulation scenario resources including scenarios, scenario positions, scenario flags, and scenario rubric grade agents",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=TEST_GRADE_AGENT,
        name="Test Grade",
        description="Benchmark test grading agent for evaluating model outputs against rubric standards",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("grader"),
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
        ],
    ),
    dict(
        id=TOOL_AGENT,
        name="Tool",
        description="AI agent for generating and managing tool resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
    ),
    dict(
        id=COMPOSER_AGENT,
        name="Composer",
        description="General-purpose orchestration agent for cross-cutting content, deployment, and infrastructure operations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=_role_model("text"),
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
