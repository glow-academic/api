"""Module 04 — Agent seed definitions.

Each dict maps directly to CreateAgentItem fields.
String fields (name, description) are resolved by the _impl function.

Note: Agent prompts and instructions are NOT included here — the
CreateAgentItem / create_agent_impl does not support prompt/instruction
junctions. These must be added separately after initial creation.
"""

from uuid import UUID

from database.seeds.models import GPT_5_1

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
ATTEMPT_INSIGHT_AGENT = UUID("018f0005-0001-7000-8000-000000000001")
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
TEST_INSIGHT_AGENT = UUID("018f0005-0001-7000-8000-000000000002")
TOOL_AGENT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

agents = [
    dict(
        id=ACTIVITY_AGENT,
        name="Activity",
        description="Analytical insights agent for real-time activity monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=AGENT_AGENT,
        name="Agent",
        description="AI agent for generating and managing agent resources including names, descriptions, flags, departments, prompts, instructions, models, and tools using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=ATTEMPT_CHAT_AGENT,
        name="Attempt Chat",
        description="Conversational AI agent for conducting training dialogues as personas",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=ATTEMPT_GRADE_AGENT,
        name="Attempt Grade",
        description="Grading and evaluation agent for analyzing training attempt performance",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=ATTEMPT_INSIGHT_AGENT,
        name="Attempt Insight",
        description="AI agent for generating analytical insights about individual training attempts including performance, conversation quality, and skill development",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=AUTH_AGENT,
        name="Auth",
        description="AI agent for generating and managing auth resources including names, descriptions, flags, protocols, slugs, and items using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=BENCHMARK_AGENT,
        name="Benchmark",
        description="AI agent for generating analytical insights about benchmark evaluation results including cross-model performance and scoring quality",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=CHAT_AGENT,
        name="Chat",
        description="AI agent for creating and managing training chat sessions with persona-driven scenario conversations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=COHORT_AGENT,
        name="Cohort",
        description="AI agent for generating and managing cohort resources including names, descriptions, flags, departments, personas, and scenarios using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=DASHBOARD_AGENT,
        name="Dashboard",
        description="Analytical insights agent for high-level organizational KPIs and trends",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=DEPARTMENT_AGENT,
        name="Department",
        description="AI agent for generating and managing department resources including names, descriptions, flags, and settings using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=DOCUMENT_AGENT,
        name="Document",
        description="Agent for generating and working with documents, templates, and structured content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=EVAL_AGENT,
        name="Eval",
        description="AI agent for generating and managing eval resources including names, descriptions, flags, departments, scenarios, rubrics, and various eval-specific resources using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=FIELD_AGENT,
        name="Field",
        description="AI agent for generating and managing field resources including names, descriptions, flags, departments, and conditional parameters using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=GROUP_AGENT,
        name="Group",
        description="Analytical insights agent for group-level analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=HEALTH_AGENT,
        name="Health",
        description="Analytical insights agent for system health monitoring",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=HOME_AGENT,
        name="Home",
        description="Navigation and recommendation agent for home page overview",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=INVOCATION_AGENT,
        name="Invocation",
        description="AI agent for creating and managing benchmark invocations with model and tool configurations",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=LEADERBOARD_AGENT,
        name="Leaderboard",
        description="Analytical insights agent for performance rankings",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=MODEL_AGENT,
        name="Model",
        description="AI agent for generating and managing model resources including names, descriptions, flags, departments, endpoints, keys, modalities, and providers using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PARAMETER_AGENT,
        name="Parameter",
        description="AI agent for generating and managing parameter resources including names, descriptions, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PERSONA_AGENT,
        name="Persona",
        description="AI agent for generating and managing persona resources including names, descriptions, colors, icons, instructions, examples, flags, departments, and fields using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PRACTICE_AGENT,
        name="Practice",
        description="Navigation and recommendation agent for practice mode entry point",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PRICING_AGENT,
        name="Pricing",
        description="Analytical insights agent for cost analytics and billing breakdowns",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PROFILE_AGENT,
        name="Profile",
        description="AI agent for generating and managing profile resources including names, descriptions, flags, departments, emails, cohorts, and request limits using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=PROVIDER_AGENT,
        name="Provider",
        description="AI agent for generating and managing provider resources including names, descriptions, flags, and endpoints using GPT-5.1",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=RECORD_AGENT,
        name="Record",
        description="Analytical insights agent for individual training record analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=REPORTS_AGENT,
        name="Reports",
        description="Analytical insights agent for detailed training outcome reports",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=RUBRIC_AGENT,
        name="Rubric",
        description="Agent for generating rubric descriptions and grid cell content",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SCENARIO_AGENT,
        name="Scenario",
        description="Helps create distinct scenarios for chat interactions.",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SCENARIO_IMAGE_AGENT,
        name="Scenario Image",
        description="Image generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SCENARIO_VIDEO_AGENT,
        name="Scenario Video",
        description="Video generation agent for creating scenario visuals",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SESSION_AGENT,
        name="Session",
        description="Analytical insights agent for individual training session analytics",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SETTING_AGENT,
        name="Setting",
        description="AI agent for generating and managing setting resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=SIMULATION_AGENT,
        name="Simulation",
        description="AI agent for generating and managing simulation scenario resources including scenarios, scenario positions, scenario flags, and scenario rubric grade agents",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=TEST_GRADE_AGENT,
        name="Test Grade",
        description="Benchmark test grading agent for evaluating model outputs against rubric standards",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=TEST_INSIGHT_AGENT,
        name="Test Insight",
        description="AI agent for generating analytical insights about benchmark test results including model performance, rubric evaluation, and scoring quality",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
    dict(
        id=TOOL_AGENT,
        name="Tool",
        description="AI agent for generating and managing tool resources",
        flag_ids=[AGENT_ACTIVE_FLAG],
        model_ids=[GPT_5_1],
    ),
]
