"""Fresh setting seed — platform default with no departments.

Creates a setting with all systems enabled, default thresholds,
auth providers, and the fresh superadmin profile linked.
This gives a working login screen out of the box.
"""

from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
    PROVIDER_KEY_IDS,
)
from database.seeds.ids import sid
from database.seeds.logins import (
    AUTH_LOGIN_IDS,
    build_profile_logins,
)
from database.seeds.setups.fresh.profiles import FRESH_SUPERADMIN_RESOURCE
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
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

ALL_SYSTEMS = [
    ACTIVITY_SYSTEM, AGENT_SYSTEM, ATTEMPT_CHAT_SYSTEM, ATTEMPT_GRADE_SYSTEM,
    AUTH_SYSTEM, BENCHMARK_SYSTEM, CHAT_SYSTEM,
    COHORT_SYSTEM, COMPOSER_SYSTEM, DASHBOARD_SYSTEM, DEPARTMENT_SYSTEM,
    DOCUMENT_SYSTEM, EVAL_SYSTEM, FIELD_SYSTEM, GROUP_SYSTEM, HEALTH_SYSTEM,
    HOME_SYSTEM, INVOCATION_SYSTEM, LEADERBOARD_SYSTEM, MODEL_SYSTEM,
    PARAMETER_SYSTEM, PERSONA_SYSTEM, PRACTICE_SYSTEM, PRICING_SYSTEM,
    PROFILE_SYSTEM, PROVIDER_SYSTEM, RECORD_SYSTEM, REPORTS_SYSTEM,
    RUBRIC_SYSTEM, SCENARIO_SYSTEM, SESSION_SYSTEM, SETTING_SYSTEM,
    SIMULATION_SYSTEM, TEST_GRADE_SYSTEM, TOOL_SYSTEM,
]

# ---------------------------------------------------------------------------
# Logins — auth logins from config + profile logins from linked profiles
# ---------------------------------------------------------------------------

_PROFILE_LOGINS = build_profile_logins([
    dict(name="Default Superadmin", resource_id=FRESH_SUPERADMIN_RESOURCE),
])
FRESH_LOGINS_IDS = AUTH_LOGIN_IDS + [lg["id"] for lg in _PROFILE_LOGINS]
FRESH_LOGINS = _PROFILE_LOGINS  # auth logins are in AUTH_LOGINS (logins.py)

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

FRESH_SETTING = sid("fresh/setting/default")
FRESH_SETTING_RESOURCE = sid("fresh/setting-resource/default")

# ---------------------------------------------------------------------------
# Setting definition
# ---------------------------------------------------------------------------

settings = [
    dict(
        id=FRESH_SETTING,
        resource_id=FRESH_SETTING_RESOURCE,
        name="Default Settings",
        description="Platform default settings — active on fresh deployments with no departments configured.",
        active_flag=True,
        department_ids=None,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS or None,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS or None,
        provider_key_ids=PROVIDER_KEY_IDS or None,
        system_ids=ALL_SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        logins_ids=FRESH_LOGINS_IDS or None,
    ),
]
