"""Module 10 — System seed definitions.

Systems use tool-level create (create_system), not _impl.
Each dict maps to create_system parameters: name, description, agent_ids, id.
"""

from uuid import UUID

# ---------------------------------------------------------------------------
# Referenced IDs from module 04 agents
# ---------------------------------------------------------------------------
# Agent resource IDs (deterministic via sid())
from database.seeds.agents import (
    ACTIVITY_AGENT_RESOURCE,
    AGENT_AGENT_RESOURCE,
    ATTEMPT_CHAT_AGENT_RESOURCE,
    ATTEMPT_CHAT_AGENT_2_RESOURCE,
    ATTEMPT_GRADE_AGENT_RESOURCE,
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
    TEST_GRADE_AGENT_RESOURCE,
    TOOL_AGENT_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ACTIVITY_SYSTEM = UUID("019caf25-99c7-78a6-849d-1258f99e47e4")
AGENT_SYSTEM = UUID("019caf25-99c8-7bba-946c-e6b9d55d2fc3")
ATTEMPT_CHAT_SYSTEM = UUID("019caf25-99ca-7f95-9038-206fe1734be3")
ATTEMPT_GRADE_SYSTEM = UUID("019caf25-99cb-700e-b879-41628a9218c5")
COMPOSER_SYSTEM = UUID("019daf25-0000-7000-8000-000000000001")
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
TOOL_SYSTEM = UUID("019caf25-99f3-7408-b7d0-968fe57800f7")

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
        description="System for attempt-chat agents",
        agent_ids=[ATTEMPT_CHAT_AGENT_RESOURCE],
    ),
    dict(
        id=ATTEMPT_GRADE_SYSTEM,
        name="Attempt Grade System",
        description="System for attempt-grade agents",
        agent_ids=[ATTEMPT_GRADE_AGENT_RESOURCE],
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
        id=TEST_GRADE_SYSTEM,
        name="Test Grade System",
        description="System for test-grade agents",
        agent_ids=[TEST_GRADE_AGENT_RESOURCE],
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
