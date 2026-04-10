"""Module 08 — Eval seed definitions.

Each dict maps directly to CreateEvalItem fields.
String fields (name, description) are resolved by the _impl function.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Referenced IDs from module 01 resources
# ---------------------------------------------------------------------------

# Flags (from database/seeds/resources/flags.py)
GROUPS_FLAG = sid("flag/groups")
DYNAMIC_FLAG = sid("flag/dynamic")
EVAL_ACTIVE_FLAG = sid("flag/eval-active")

# Common flag set shared by all evals
_EVAL_FLAGS = [GROUPS_FLAG, DYNAMIC_FLAG, EVAL_ACTIVE_FLAG]

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

RUN_EVAL = sid("eval/run")
GROUP_EVAL = sid("eval/group")
AGENT_AGENT_EVAL = sid("eval/agent-agent")
AUTH_AGENT_EVAL = sid("eval/auth-agent")
BENCHMARK_AGENT_EVAL = sid("eval/benchmark-agent")
CHAT_AGENT_AGENT_EVAL = sid("eval/chat-agent-agent")
COHORT_AGENT_EVAL = sid("eval/cohort-agent")
DEPARTMENT_AGENT_EVAL = sid("eval/department-agent")
DOCUMENT_AGENT_EVAL = sid("eval/document-agent")
EVAL_AGENT_EVAL = sid("eval/eval-agent")
FIELD_AGENT_EVAL = sid("eval/field-agent")
GRADE_AGENT_AGENT_EVAL = sid("eval/grade-agent-agent")
MODEL_AGENT_EVAL = sid("eval/model-agent")
PARAMETER_AGENT_EVAL = sid("eval/parameter-agent")
PERSONA_AGENT_EVAL = sid("eval/persona-agent")
PROFILE_AGENT_EVAL = sid("eval/profile-agent")
PROVIDER_AGENT_EVAL = sid("eval/provider-agent")
RUBRIC_AGENT_EVAL = sid("eval/rubric-agent")
SCENARIO_AGENT_EVAL = sid("eval/scenario-agent")
SETTING_AGENT_EVAL = sid("eval/setting-agent")
SIMULATION_AGENT_EVAL = sid("eval/simulation-agent")
TOOL_AGENT_EVAL = sid("eval/tool-agent")
TRAINING_AGENT_EVAL = sid("eval/training-agent")

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
