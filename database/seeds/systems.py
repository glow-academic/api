"""Module 10 — System seed definitions.

Systems use tool-level create (create_system), not _impl.
Each dict maps to create_system parameters: name, description, agent_ids, id.
"""

from uuid import UUID

# ---------------------------------------------------------------------------
# Referenced IDs from module 04 agents
# ---------------------------------------------------------------------------
# Agent resource IDs (created by _impl, artifact ID = resource ID)
from database.seeds.agents import (
    ACTIVITY_AGENT,
    AGENT_AGENT,
    ATTEMPT_CHAT_AGENT,
    ATTEMPT_CHAT_AGENT_2,
    ATTEMPT_GRADE_AGENT,
    ATTEMPT_INSIGHT_AGENT,
    AUTH_AGENT,
    BENCHMARK_AGENT,
    CHAT_AGENT,
    COHORT_AGENT,
    DASHBOARD_AGENT,
    DEPARTMENT_AGENT,
    DOCUMENT_AGENT,
    EVAL_AGENT,
    FIELD_AGENT,
    GROUP_AGENT,
    HEALTH_AGENT,
    HOME_AGENT,
    INVOCATION_AGENT,
    LEADERBOARD_AGENT,
    MODEL_AGENT,
    PARAMETER_AGENT,
    PERSONA_AGENT,
    PRACTICE_AGENT,
    PRICING_AGENT,
    PROFILE_AGENT,
    PROVIDER_AGENT,
    RECORD_AGENT,
    REPORTS_AGENT,
    RUBRIC_AGENT,
    SCENARIO_AGENT,
    SCENARIO_IMAGE_AGENT,
    SCENARIO_VIDEO_AGENT,
    SESSION_AGENT,
    SETTING_AGENT,
    SIMULATION_AGENT,
    TEST_GRADE_AGENT,
    TEST_INSIGHT_AGENT,
    TOOL_AGENT,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ACTIVITY_SYSTEM = UUID("019caf25-99c7-78a6-849d-1258f99e47e4")
AGENT_SYSTEM = UUID("019caf25-99c8-7bba-946c-e6b9d55d2fc3")
ATTEMPT_CHAT_SYSTEM = UUID("019caf25-99ca-7f95-9038-206fe1734be3")
ATTEMPT_GRADE_SYSTEM = UUID("019caf25-99cb-700e-b879-41628a9218c5")
ATTEMPT_INSIGHT_SYSTEM = UUID("019caf25-99cc-7cc3-a040-981957508b2a")
AUTH_SYSTEM = UUID("019caf25-99cd-7470-bc4b-7eb189b96d43")
BENCHMARK_SYSTEM = UUID("019caf25-99cf-7087-81ee-58450c4a9aca")
CHAT_SYSTEM = UUID("019caf25-99d0-7d2c-bfba-49be9f4acd87")
COHORT_SYSTEM = UUID("019caf25-99d1-771d-a01f-80f8aae924df")
DASHBOARD_SYSTEM = UUID("019caf25-99d2-752b-ab22-5f9455aa1e9a")
DEPARTMENT_SYSTEM = UUID("019caf25-99d4-7fb7-8cec-e9a0de527479")
DOCUMENT_SYSTEM = UUID("019caf25-99d5-7ff1-a78c-485cbcd14b60")
EVAL_SYSTEM = UUID("019caf25-99d6-70d6-90eb-f580991fcf89")
FIELD_SYSTEM = UUID("019caf25-99d7-792a-a47b-246dd0a84352")
GROUP_SYSTEM = UUID("019caf25-99d9-73dc-a8be-a47def47c3e0")
HEALTH_SYSTEM = UUID("019caf25-99da-7af2-875a-9c8eb8fd70e9")
HOME_SYSTEM = UUID("019caf25-99db-7090-87a2-0c2dff148860")
INVOCATION_SYSTEM = UUID("019caf25-99dc-73fa-848e-fcc5947b6bb1")
LEADERBOARD_SYSTEM = UUID("019caf25-99de-7c11-9dd7-a8878ef28a07")
MODEL_SYSTEM = UUID("019caf25-99df-716b-abc9-a4c3ba2f32c8")
PARAMETER_SYSTEM = UUID("019caf25-99e0-7e2c-9f64-37bde94a00c6")
PERSONA_SYSTEM = UUID("019caf25-99e1-717c-b4ea-8a6055664887")
PRACTICE_SYSTEM = UUID("019caf25-99e3-723d-920c-78e5ac8f19dd")
PRICING_SYSTEM = UUID("019caf25-99e4-7571-8bb7-155d53173005")
PROFILE_SYSTEM = UUID("019caf25-99e5-75e8-b0f1-a5bd20b35bfa")
PROVIDER_SYSTEM = UUID("019caf25-99e6-7886-96fe-71a0bb6090d1")
RECORD_SYSTEM = UUID("019caf25-99e8-7cd5-8d61-a7800f1a6686")
REPORTS_SYSTEM = UUID("019caf25-99e9-72be-8c27-e3f264eeefa4")
RUBRIC_SYSTEM = UUID("019caf25-99ea-7f17-8bac-4ed76165c512")
SCENARIO_SYSTEM = UUID("019caf25-99ec-727f-be3c-4224ee4f9bef")
SESSION_SYSTEM = UUID("019caf25-99ed-79c0-926c-d302897f4322")
SETTING_SYSTEM = UUID("019caf25-99ee-7f5e-934d-1c9eaeb52f24")
SIMULATION_SYSTEM = UUID("019caf25-99ef-7358-87a9-29cb15f52fd3")
TEST_GRADE_SYSTEM = UUID("019caf25-99f2-7ea3-8a59-24fcd0ff8b8c")
TEST_INSIGHT_SYSTEM = UUID("019caf25-99f1-7230-bee2-f5e15bd56400")
TOOL_SYSTEM = UUID("019caf25-99f3-7408-b7d0-968fe57800f7")

# ---------------------------------------------------------------------------
# System definitions
# ---------------------------------------------------------------------------

systems = [
    dict(
        id=ACTIVITY_SYSTEM,
        name="Activity System",
        description="System for activity agents",
        agent_ids=[ACTIVITY_AGENT],
    ),
    dict(
        id=AGENT_SYSTEM,
        name="Agent System",
        description="System for agent agents",
        agent_ids=[AGENT_AGENT],
    ),
    dict(
        id=ATTEMPT_CHAT_SYSTEM,
        name="Attempt Chat System",
        description="System for attempt-chat agents",
        agent_ids=[ATTEMPT_CHAT_AGENT, ATTEMPT_CHAT_AGENT_2],
    ),
    dict(
        id=ATTEMPT_GRADE_SYSTEM,
        name="Attempt Grade System",
        description="System for attempt-grade agents",
        agent_ids=[ATTEMPT_GRADE_AGENT],
    ),
    dict(
        id=ATTEMPT_INSIGHT_SYSTEM,
        name="Attempt Insight System",
        description="System for attempt-insight agents",
        agent_ids=[ATTEMPT_INSIGHT_AGENT],
    ),
    dict(
        id=AUTH_SYSTEM,
        name="Auth System",
        description="System for auth agents",
        agent_ids=[AUTH_AGENT],
    ),
    dict(
        id=BENCHMARK_SYSTEM,
        name="Benchmark System",
        description="System for benchmark agents",
        agent_ids=[BENCHMARK_AGENT],
    ),
    dict(
        id=CHAT_SYSTEM,
        name="Chat System",
        description="System for chat agents",
        agent_ids=[CHAT_AGENT],
    ),
    dict(
        id=COHORT_SYSTEM,
        name="Cohort System",
        description="System for cohort agents",
        agent_ids=[COHORT_AGENT],
    ),
    dict(
        id=DASHBOARD_SYSTEM,
        name="Dashboard System",
        description="System for dashboard agents",
        agent_ids=[DASHBOARD_AGENT],
    ),
    dict(
        id=DEPARTMENT_SYSTEM,
        name="Department System",
        description="System for department agents",
        agent_ids=[DEPARTMENT_AGENT],
    ),
    dict(
        id=DOCUMENT_SYSTEM,
        name="Document System",
        description="System for document agents",
        agent_ids=[DOCUMENT_AGENT],
    ),
    dict(
        id=EVAL_SYSTEM,
        name="Eval System",
        description="System for eval agents",
        agent_ids=[EVAL_AGENT],
    ),
    dict(
        id=FIELD_SYSTEM,
        name="Field System",
        description="System for field agents",
        agent_ids=[FIELD_AGENT],
    ),
    dict(
        id=GROUP_SYSTEM,
        name="Group System",
        description="System for group agents",
        agent_ids=[GROUP_AGENT],
    ),
    dict(
        id=HEALTH_SYSTEM,
        name="Health System",
        description="System for health agents",
        agent_ids=[HEALTH_AGENT],
    ),
    dict(
        id=HOME_SYSTEM,
        name="Home System",
        description="System for home agents",
        agent_ids=[HOME_AGENT],
    ),
    dict(
        id=INVOCATION_SYSTEM,
        name="Invocation System",
        description="System for invocation agents",
        agent_ids=[INVOCATION_AGENT],
    ),
    dict(
        id=LEADERBOARD_SYSTEM,
        name="Leaderboard System",
        description="System for leaderboard agents",
        agent_ids=[LEADERBOARD_AGENT],
    ),
    dict(
        id=MODEL_SYSTEM,
        name="Model System",
        description="System for model agents",
        agent_ids=[MODEL_AGENT],
    ),
    dict(
        id=PARAMETER_SYSTEM,
        name="Parameter System",
        description="System for parameter agents",
        agent_ids=[PARAMETER_AGENT],
    ),
    dict(
        id=PERSONA_SYSTEM,
        name="Persona System",
        description="System for persona agents",
        agent_ids=[PERSONA_AGENT],
    ),
    dict(
        id=PRACTICE_SYSTEM,
        name="Practice System",
        description="System for practice agents",
        agent_ids=[PRACTICE_AGENT],
    ),
    dict(
        id=PRICING_SYSTEM,
        name="Pricing System",
        description="System for pricing agents",
        agent_ids=[PRICING_AGENT],
    ),
    dict(
        id=PROFILE_SYSTEM,
        name="Profile System",
        description="System for profile agents",
        agent_ids=[PROFILE_AGENT],
    ),
    dict(
        id=PROVIDER_SYSTEM,
        name="Provider System",
        description="System for provider agents",
        agent_ids=[PROVIDER_AGENT],
    ),
    dict(
        id=RECORD_SYSTEM,
        name="Record System",
        description="System for record agents",
        agent_ids=[RECORD_AGENT],
    ),
    dict(
        id=REPORTS_SYSTEM,
        name="Reports System",
        description="System for reports agents",
        agent_ids=[REPORTS_AGENT],
    ),
    dict(
        id=RUBRIC_SYSTEM,
        name="Rubric System",
        description="System for rubric agents",
        agent_ids=[RUBRIC_AGENT],
    ),
    dict(
        id=SCENARIO_SYSTEM,
        name="Scenario System",
        description="System for scenario agents",
        agent_ids=[SCENARIO_AGENT, SCENARIO_IMAGE_AGENT, SCENARIO_VIDEO_AGENT],
    ),
    dict(
        id=SESSION_SYSTEM,
        name="Session System",
        description="System for session agents",
        agent_ids=[SESSION_AGENT],
    ),
    dict(
        id=SETTING_SYSTEM,
        name="Setting System",
        description="System for setting agents",
        agent_ids=[SETTING_AGENT],
    ),
    dict(
        id=SIMULATION_SYSTEM,
        name="Simulation System",
        description="System for simulation agents",
        agent_ids=[SIMULATION_AGENT],
    ),
    dict(
        id=TEST_GRADE_SYSTEM,
        name="Test Grade System",
        description="System for test-grade agents",
        agent_ids=[TEST_GRADE_AGENT],
    ),
    dict(
        id=TEST_INSIGHT_SYSTEM,
        name="Test Insight System",
        description="System for test-insight agents",
        agent_ids=[TEST_INSIGHT_AGENT],
    ),
    dict(
        id=TOOL_SYSTEM,
        name="Tool System",
        description="System for tool agents",
        agent_ids=[TOOL_AGENT],
    ),
]
