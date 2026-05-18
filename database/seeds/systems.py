"""Module 10 — System seed definitions.

Systems use tool-level create (create_system), not _impl.
Each dict maps to create_system parameters: name, description, agent_ids, id.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Referenced IDs from module 04 agents
# ---------------------------------------------------------------------------
# Agent resource IDs (deterministic via sid())
from database.seeds.agents import (
    ACTIVITY_AGENT_RESOURCE,
    AGENT_AGENT_RESOURCE,
    ATTEMPT_AGENT_RESOURCE,
    ATTEMPT_AUDIO_AGENT_RESOURCE,
    ATTEMPT_REALTIME_AGENT_RESOURCE,
    AUTH_AGENT_RESOURCE,
    BENCHMARK_AGENT_RESOURCE,
    CHAT_AGENT_RESOURCE,
    COHORT_AGENT_RESOURCE,
    COMPOSER_AGENT_RESOURCE,
    DASHBOARD_AGENT_RESOURCE,
    DEPARTMENT_AGENT_RESOURCE,
    DOCUMENT_AGENT_RESOURCE,
    EVAL_AGENT_RESOURCE,
    FIELD_AGENT_RESOURCE,
    GROUP_AGENT_RESOURCE,
    HEALTH_AGENT_RESOURCE,
    HOME_AGENT_RESOURCE,
    INVOCATION_AGENT_RESOURCE,
    LEADERBOARD_AGENT_RESOURCE,
    MODEL_AGENT_RESOURCE,
    PARAMETER_AGENT_RESOURCE,
    PERSONA_AGENT_RESOURCE,
    PERSONA_GEMINI_AGENT_RESOURCE,
    PRACTICE_AGENT_RESOURCE,
    PRICING_AGENT_RESOURCE,
    PROFILE_AGENT_RESOURCE,
    PROVIDER_AGENT_RESOURCE,
    RECORD_AGENT_RESOURCE,
    REPORTS_AGENT_RESOURCE,
    RUBRIC_AGENT_RESOURCE,
    SCENARIO_AGENT_RESOURCE,
    SCENARIO_IMAGE_AGENT_RESOURCE,
    SCENARIO_VIDEO_AGENT_RESOURCE,
    SESSION_AGENT_RESOURCE,
    SETTING_AGENT_RESOURCE,
    SIMULATION_AGENT_RESOURCE,
    TEST_AGENT_RESOURCE,
    TEST_GRADE_AGENT_RESOURCE,
    TOOL_AGENT_RESOURCE,
    TRANSCRIBE_AGENT_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ACTIVITY_SYSTEM = sid("system/activity")
AGENT_SYSTEM = sid("system/agent")
ATTEMPT_CHAT_SYSTEM = sid("system/attempt-chat")
ATTEMPT_GRADE_SYSTEM = sid("system/attempt-grade")
COMPOSER_SYSTEM = sid("system/composer")
AUTH_SYSTEM = sid("system/auth")
BENCHMARK_SYSTEM = sid("system/benchmark")
CHAT_SYSTEM = sid("system/chat")
COHORT_SYSTEM = sid("system/cohort")
DASHBOARD_SYSTEM = sid("system/dashboard")
DEPARTMENT_SYSTEM = sid("system/department")
DOCUMENT_SYSTEM = sid("system/document")
EVAL_SYSTEM = sid("system/eval")
FIELD_SYSTEM = sid("system/field")
GROUP_SYSTEM = sid("system/group")
HEALTH_SYSTEM = sid("system/health")
HOME_SYSTEM = sid("system/home")
INVOCATION_SYSTEM = sid("system/invocation")
LEADERBOARD_SYSTEM = sid("system/leaderboard")
MODEL_SYSTEM = sid("system/model")
PARAMETER_SYSTEM = sid("system/parameter")
PERSONA_SYSTEM = sid("system/persona")
PRACTICE_SYSTEM = sid("system/practice")
PRICING_SYSTEM = sid("system/pricing")
PROFILE_SYSTEM = sid("system/profile")
PROVIDER_SYSTEM = sid("system/provider")
RECORD_SYSTEM = sid("system/record")
REPORTS_SYSTEM = sid("system/reports")
RUBRIC_SYSTEM = sid("system/rubric")
SCENARIO_SYSTEM = sid("system/scenario")
SESSION_SYSTEM = sid("system/session")
SETTING_SYSTEM = sid("system/setting")
SIMULATION_SYSTEM = sid("system/simulation")
TEST_SYSTEM = sid("system/test")
TEST_GRADE_SYSTEM = sid("system/test-grade")
TOOL_SYSTEM = sid("system/tool")

# ---------------------------------------------------------------------------
# System definitions
# ---------------------------------------------------------------------------

systems = [
    dict(
        id=ACTIVITY_SYSTEM,
        name="Activity System",
        description="System for activity agents",
        agent_ids=[ACTIVITY_AGENT_RESOURCE],
    ),
    dict(
        id=AGENT_SYSTEM,
        name="Agent System",
        description="System for agent agents",
        agent_ids=[AGENT_AGENT_RESOURCE],
    ),
    dict(
        id=ATTEMPT_CHAT_SYSTEM,
        name="Attempt Chat System",
        description="System for attempt-chat agents — text + audio (TTS) + realtime + transcribe",
        agent_ids=[
            ATTEMPT_AGENT_RESOURCE,
            ATTEMPT_AUDIO_AGENT_RESOURCE,
            ATTEMPT_REALTIME_AGENT_RESOURCE,
            TRANSCRIBE_AGENT_RESOURCE,
        ],
    ),
    dict(
        id=ATTEMPT_GRADE_SYSTEM,
        name="Attempt Grade System",
        description="System for attempt-grade agents",
        agent_ids=[ATTEMPT_AGENT_RESOURCE],
    ),
    dict(
        id=AUTH_SYSTEM,
        name="Auth System",
        description="System for auth agents",
        agent_ids=[AUTH_AGENT_RESOURCE],
    ),
    dict(
        id=BENCHMARK_SYSTEM,
        name="Benchmark System",
        description="System for benchmark agents",
        agent_ids=[BENCHMARK_AGENT_RESOURCE],
    ),
    dict(
        id=CHAT_SYSTEM,
        name="Chat System",
        description="System for chat agents",
        agent_ids=[CHAT_AGENT_RESOURCE],
    ),
    dict(
        id=COHORT_SYSTEM,
        name="Cohort System",
        description="System for cohort agents",
        agent_ids=[COHORT_AGENT_RESOURCE],
    ),
    dict(
        id=DASHBOARD_SYSTEM,
        name="Dashboard System",
        description="System for dashboard agents",
        agent_ids=[DASHBOARD_AGENT_RESOURCE],
    ),
    dict(
        id=DEPARTMENT_SYSTEM,
        name="Department System",
        description="System for department agents",
        agent_ids=[DEPARTMENT_AGENT_RESOURCE],
    ),
    dict(
        id=DOCUMENT_SYSTEM,
        name="Document System",
        description="System for document agents",
        agent_ids=[DOCUMENT_AGENT_RESOURCE],
    ),
    dict(
        id=EVAL_SYSTEM,
        name="Eval System",
        description="System for eval agents",
        agent_ids=[EVAL_AGENT_RESOURCE],
    ),
    dict(
        id=FIELD_SYSTEM,
        name="Field System",
        description="System for field agents",
        agent_ids=[FIELD_AGENT_RESOURCE],
    ),
    dict(
        id=GROUP_SYSTEM,
        name="Group System",
        description="System for group agents",
        agent_ids=[GROUP_AGENT_RESOURCE],
    ),
    dict(
        id=HEALTH_SYSTEM,
        name="Health System",
        description="System for health agents",
        agent_ids=[HEALTH_AGENT_RESOURCE],
    ),
    dict(
        id=HOME_SYSTEM,
        name="Home System",
        description="System for home agents",
        agent_ids=[HOME_AGENT_RESOURCE],
    ),
    dict(
        id=INVOCATION_SYSTEM,
        name="Invocation System",
        description="System for invocation agents",
        agent_ids=[INVOCATION_AGENT_RESOURCE],
    ),
    dict(
        id=LEADERBOARD_SYSTEM,
        name="Leaderboard System",
        description="System for leaderboard agents",
        agent_ids=[LEADERBOARD_AGENT_RESOURCE],
    ),
    dict(
        id=MODEL_SYSTEM,
        name="Model System",
        description="System for model agents",
        agent_ids=[MODEL_AGENT_RESOURCE],
    ),
    dict(
        id=PARAMETER_SYSTEM,
        name="Parameter System",
        description="System for parameter agents",
        agent_ids=[PARAMETER_AGENT_RESOURCE],
    ),
    dict(
        id=PERSONA_SYSTEM,
        name="Persona System",
        description="System for persona agents",
        agent_ids=[PERSONA_AGENT_RESOURCE],
    ),
    dict(
        id=PRACTICE_SYSTEM,
        name="Practice System",
        description="System for practice agents",
        agent_ids=[PRACTICE_AGENT_RESOURCE],
    ),
    dict(
        id=PRICING_SYSTEM,
        name="Pricing System",
        description="System for pricing agents",
        agent_ids=[PRICING_AGENT_RESOURCE],
    ),
    dict(
        id=PROFILE_SYSTEM,
        name="Profile System",
        description="System for profile agents",
        agent_ids=[PROFILE_AGENT_RESOURCE],
    ),
    dict(
        id=PROVIDER_SYSTEM,
        name="Provider System",
        description="System for provider agents",
        agent_ids=[PROVIDER_AGENT_RESOURCE],
    ),
    dict(
        id=RECORD_SYSTEM,
        name="Record System",
        description="System for record agents",
        agent_ids=[RECORD_AGENT_RESOURCE],
    ),
    dict(
        id=REPORTS_SYSTEM,
        name="Reports System",
        description="System for reports agents",
        agent_ids=[REPORTS_AGENT_RESOURCE],
    ),
    dict(
        id=RUBRIC_SYSTEM,
        name="Rubric System",
        description="System for rubric agents",
        agent_ids=[RUBRIC_AGENT_RESOURCE],
    ),
    dict(
        id=SCENARIO_SYSTEM,
        name="Scenario System",
        description="System for scenario agents",
        agent_ids=[SCENARIO_AGENT_RESOURCE, SCENARIO_IMAGE_AGENT_RESOURCE, SCENARIO_VIDEO_AGENT_RESOURCE],
    ),
    dict(
        id=SESSION_SYSTEM,
        name="Session System",
        description="System for session agents",
        agent_ids=[SESSION_AGENT_RESOURCE],
    ),
    dict(
        id=SETTING_SYSTEM,
        name="Setting System",
        description="System for setting agents",
        agent_ids=[SETTING_AGENT_RESOURCE],
    ),
    dict(
        id=SIMULATION_SYSTEM,
        name="Simulation System",
        description="System for simulation agents",
        agent_ids=[SIMULATION_AGENT_RESOURCE],
    ),
    dict(
        id=TEST_SYSTEM,
        name="Test System",
        description="System for the test orchestrator agent — materialization + lifecycle",
        agent_ids=[TEST_AGENT_RESOURCE],
    ),
    dict(
        id=TEST_GRADE_SYSTEM,
        name="Test Grade System",
        description="System for test-grade agents",
        # Test agent included alongside Test Grade so it's reachable when
        # this system wins the "test" scoring resource. Mirrors how
        # ATTEMPT_AGENT_RESOURCE is in both ATTEMPT_CHAT_SYSTEM and
        # ATTEMPT_GRADE_SYSTEM — keeps the orchestrator agent reachable
        # from either winning side without depending on per-system score.
        agent_ids=[TEST_AGENT_RESOURCE, TEST_GRADE_AGENT_RESOURCE],
    ),
    dict(
        id=TOOL_SYSTEM,
        name="Tool System",
        description="System for tool agents",
        agent_ids=[TOOL_AGENT_RESOURCE],
    ),
    dict(
        id=COMPOSER_SYSTEM,
        name="Composer System",
        description="System for cross-cutting content, deployment, and infrastructure operations",
        agent_ids=[COMPOSER_AGENT_RESOURCE],
    ),
]
