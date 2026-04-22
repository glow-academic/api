"""Default setting — baked into fresh.sql.gz.

Creates a setting with no department attached, all systems enabled,
default thresholds, and the default superadmin profile linked.
Auth providers are dynamically included from glow-deploy.yaml config.
This gives a working login screen out of the box on fresh deploys.
"""

from database.seeds.ids import sid
from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
)
from database.seeds.logins import (
    AUTH_LOGIN_IDS,
    build_profile_logins,
)
from database.seeds.profiles import SEED_PROFILE_RESOURCE
from database.seeds.systems import (
    ACTIVITY_SYSTEM,
    AGENT_SYSTEM,
    ATTEMPT_CHAT_SYSTEM,
    ATTEMPT_GRADE_SYSTEM,
    AUTH_SYSTEM,
    BENCHMARK_SYSTEM,
    CHAT_SYSTEM,
    COHORT_SYSTEM,
    COMPOSER_SYSTEM,
    DASHBOARD_SYSTEM,
    DEPARTMENT_SYSTEM,
    DOCUMENT_SYSTEM,
    EVAL_SYSTEM,
    FIELD_SYSTEM,
    GROUP_SYSTEM,
    HEALTH_SYSTEM,
    HOME_SYSTEM,
    INVOCATION_SYSTEM,
    LEADERBOARD_SYSTEM,
    MODEL_SYSTEM,
    PARAMETER_SYSTEM,
    PERSONA_SYSTEM,
    PRACTICE_SYSTEM,
    PRICING_SYSTEM,
    PROFILE_SYSTEM,
    PROVIDER_SYSTEM,
    RECORD_SYSTEM,
    REPORTS_SYSTEM,
    RUBRIC_SYSTEM,
    SCENARIO_SYSTEM,
    SESSION_SYSTEM,
    SETTING_SYSTEM,
    SIMULATION_SYSTEM,
    TEST_GRADE_SYSTEM,
    TOOL_SYSTEM,
)

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs (from module 01 resources)
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

# ---------------------------------------------------------------------------
# All system IDs
# ---------------------------------------------------------------------------

ALL_SYSTEMS = [
    # CRUD artifact systems (create, update, delete, generate)
    AGENT_SYSTEM,
    AUTH_SYSTEM,
    CHAT_SYSTEM,
    COHORT_SYSTEM,
    DEPARTMENT_SYSTEM,
    DOCUMENT_SYSTEM,
    EVAL_SYSTEM,
    FIELD_SYSTEM,
    MODEL_SYSTEM,
    PARAMETER_SYSTEM,
    PERSONA_SYSTEM,
    PROFILE_SYSTEM,
    PROVIDER_SYSTEM,
    RUBRIC_SYSTEM,
    SCENARIO_SYSTEM,
    SETTING_SYSTEM,
    SIMULATION_SYSTEM,
    TOOL_SYSTEM,
    # Attempt + test state machines
    ATTEMPT_CHAT_SYSTEM,
    ATTEMPT_GRADE_SYSTEM,
    TEST_GRADE_SYSTEM,
    # Orchestration
    COMPOSER_SYSTEM,
    GROUP_SYSTEM,
    INVOCATION_SYSTEM,
]

# ---------------------------------------------------------------------------
# Logins — auth logins from config + profile logins from linked profiles
# ---------------------------------------------------------------------------

_PROFILE_LOGINS = build_profile_logins([
    dict(name="Bootstrap Superadmin", resource_id=SEED_PROFILE_RESOURCE),
])
DEFAULT_LOGINS_IDS = AUTH_LOGIN_IDS + [lg["id"] for lg in _PROFILE_LOGINS]
DEFAULT_LOGINS = _PROFILE_LOGINS  # auth logins are in AUTH_LOGINS (logins.py)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

DEFAULT_SETTING = sid("default/setting")
DEFAULT_SETTING_RESOURCE = sid("default/setting-resource")

# ---------------------------------------------------------------------------
# Setting definition — no departments, no auth, just systems + thresholds + profiles
# ---------------------------------------------------------------------------

settings = [
    dict(
        id=DEFAULT_SETTING,
        resource_id=DEFAULT_SETTING_RESOURCE,
        name="Default Settings",
        description="Platform default settings — active on fresh deployments with no departments configured.",
        active_flag=True,
        department_ids=None,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS or None,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS or None,
        system_ids=ALL_SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        logins_ids=DEFAULT_LOGINS_IDS or None,
    ),
]


