"""Module 08 — Eval seed definitions.

Each dict maps directly to CreateEvalItem fields.
String fields (name, description) are resolved by the _impl function.
"""

from uuid import UUID

# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Flags (from database/seeds/resources/flags.py)
GROUPS_FLAG = UUID("019b995a-86ef-789f-94fa-2bd3e0707baa")
DYNAMIC_FLAG = UUID("019b995a-86ef-7879-89ed-3eadac3e0b84")
EVAL_ACTIVE_FLAG = UUID("019be334-bfc4-7c9d-b9f9-19eb0fc849ec")

# Common flag set shared by all evals
_EVAL_FLAGS = [GROUPS_FLAG, DYNAMIC_FLAG, EVAL_ACTIVE_FLAG]

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

RUN_EVAL = UUID("dd000051-0001-0000-0000-000000000001")
GROUP_EVAL = UUID("dd000051-0002-0000-0000-000000000001")
AGENT_AGENT_EVAL = UUID("019c4e7a-47a2-7896-9f5a-5f57ee554660")
AUTH_AGENT_EVAL = UUID("019c4e7a-479e-7b43-8b0d-556438b63229")
BENCHMARK_AGENT_EVAL = UUID("cc000004-0000-0000-0000-000000000004")
CHAT_AGENT_AGENT_EVAL = UUID("019c4e7a-47a6-7955-bfd8-48ef668e5e2b")
COHORT_AGENT_EVAL = UUID("019c4e7a-47a1-718c-accd-d11772098c08")
DEPARTMENT_AGENT_EVAL = UUID("019c4e7a-47a0-75f7-99dd-154cf20c98a2")
DOCUMENT_AGENT_EVAL = UUID("019c4e7a-479b-7da3-8534-d832cfa860ae")
EVAL_AGENT_EVAL = UUID("019c4e7a-47a7-7553-8b10-6eb4663b8f4c")
FIELD_AGENT_EVAL = UUID("019c4e7a-47a8-7e85-b75d-f4b48ab2ee19")
GRADE_AGENT_AGENT_EVAL = UUID("019c4e7a-47a8-7275-93eb-681f5cf002bb")
MODEL_AGENT_EVAL = UUID("019c4e7a-47a3-76e1-bfa9-b402c7625143")
PARAMETER_AGENT_EVAL = UUID("019c4e7a-479d-7a2b-9b03-a8c46af98ae0")
PERSONA_AGENT_EVAL = UUID("019c4e7a-47a5-716a-a626-9112bdb22e12")
PROFILE_AGENT_EVAL = UUID("019c4e7a-479f-7abc-b3ea-61e82a842163")
PROVIDER_AGENT_EVAL = UUID("019c4e7a-4794-739c-8361-b0401227847c")
RUBRIC_AGENT_EVAL = UUID("019c4e7a-479c-7c3d-bd8e-44daa22da6bc")
SCENARIO_AGENT_EVAL = UUID("019c4e7a-479a-7a20-9aab-060d29dfbe69")
SETTING_AGENT_EVAL = UUID("019c4e7a-47a1-7cd1-964f-ed3f1d0d56a6")
SIMULATION_AGENT_EVAL = UUID("019c4e7a-47a5-7d9f-9919-7e441e32a162")
TOOL_AGENT_EVAL = UUID("019c4e7a-47a4-7552-970e-bddea1ef0176")
TRAINING_AGENT_EVAL = UUID("cc000003-0000-0000-0000-000000000003")

# ---------------------------------------------------------------------------
# Eval definitions
# ---------------------------------------------------------------------------

evals = [
    dict(
        id=RUN_EVAL,
        name="Run Evaluation",
        description="Evaluates individual runs from the demo attempt.",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=GROUP_EVAL,
        name="Group Evaluation",
        description="Evaluates the chat group from the demo attempt.",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=AGENT_AGENT_EVAL,
        name="Agent Agent Evaluation",
        description="Evaluation of agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=AUTH_AGENT_EVAL,
        name="Auth Agent Evaluation",
        description="Evaluation of auth agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=BENCHMARK_AGENT_EVAL,
        name="Benchmark Agent Evaluation",
        description="Evaluation of benchmark agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=CHAT_AGENT_AGENT_EVAL,
        name="Chat Agent Agent Evaluation",
        description="Evaluation of chat agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=COHORT_AGENT_EVAL,
        name="Cohort Agent Evaluation",
        description="Evaluation of cohort agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=DEPARTMENT_AGENT_EVAL,
        name="Department Agent Evaluation",
        description="Evaluation of department agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=DOCUMENT_AGENT_EVAL,
        name="Document Agent Evaluation",
        description="Evaluation of document agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=EVAL_AGENT_EVAL,
        name="Eval Agent Evaluation",
        description="Evaluation of eval agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=FIELD_AGENT_EVAL,
        name="Field Agent Evaluation",
        description="Evaluation of field agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=GRADE_AGENT_AGENT_EVAL,
        name="Grade Agent Agent Evaluation",
        description="Evaluation of grade agent agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=MODEL_AGENT_EVAL,
        name="Model Agent Evaluation",
        description="Evaluation of model agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PARAMETER_AGENT_EVAL,
        name="Parameter Agent Evaluation",
        description="Evaluation of parameter agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PERSONA_AGENT_EVAL,
        name="Persona Agent Evaluation",
        description="Evaluation of persona agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PROFILE_AGENT_EVAL,
        name="Profile Agent Evaluation",
        description="Evaluation of profile agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=PROVIDER_AGENT_EVAL,
        name="Provider Agent Evaluation",
        description="Evaluation of provider agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=RUBRIC_AGENT_EVAL,
        name="Rubric Agent Evaluation",
        description="Evaluation of rubric agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SCENARIO_AGENT_EVAL,
        name="Scenario Agent Evaluation",
        description="Evaluation of scenario agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SETTING_AGENT_EVAL,
        name="Setting Agent Evaluation",
        description="Evaluation of setting agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=SIMULATION_AGENT_EVAL,
        name="Simulation Agent Evaluation",
        description="Evaluation of simulation agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=TOOL_AGENT_EVAL,
        name="Tool Agent Evaluation",
        description="Evaluation of tool agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
    dict(
        id=TRAINING_AGENT_EVAL,
        name="Training Agent Evaluation",
        description="Evaluation of training agent performance",
        flag_ids=_EVAL_FLAGS,
    ),
]
