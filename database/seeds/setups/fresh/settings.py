"""Fresh setting seed — platform default with no departments.

Creates a setting with all systems enabled, default thresholds,
auth providers, and the fresh superadmin profile linked.
This gives a working login screen out of the box.
"""

from uuid import UUID

from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
    AUTH_RESOURCE_ID_LIST,
    PROVIDER_KEY_IDS,
)
from database.seeds.ids import sid
from database.seeds.setups.fresh.profiles import FRESH_SUPERADMIN_RESOURCE
from database.seeds.systems import (
    ACTIVITY_SYSTEM,
    AGENT_SYSTEM,
    ATTEMPT_CHAT_SYSTEM,
    ATTEMPT_GRADE_SYSTEM,
    ATTEMPT_INSIGHT_SYSTEM,
    AUTH_SYSTEM,
    BENCHMARK_SYSTEM,
    CHAT_SYSTEM,
    COHORT_SYSTEM,
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
    TEST_INSIGHT_SYSTEM,
    TOOL_SYSTEM,
)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = UUID("019b995b-5308-7a8e-9d31-b08127742439")  # 85
THRESHOLD_WARNING = UUID("019b995b-5309-714f-a5f6-5614613257b1")  # 80
THRESHOLD_DANGER = UUID("019b995b-5309-74df-991a-c28980b294f2")  # 70

ALL_SYSTEMS = [
    ACTIVITY_SYSTEM, AGENT_SYSTEM, ATTEMPT_CHAT_SYSTEM, ATTEMPT_GRADE_SYSTEM,
    ATTEMPT_INSIGHT_SYSTEM, AUTH_SYSTEM, BENCHMARK_SYSTEM, CHAT_SYSTEM,
    COHORT_SYSTEM, DASHBOARD_SYSTEM, DEPARTMENT_SYSTEM, DOCUMENT_SYSTEM,
    EVAL_SYSTEM, FIELD_SYSTEM, GROUP_SYSTEM, HEALTH_SYSTEM, HOME_SYSTEM,
    INVOCATION_SYSTEM, LEADERBOARD_SYSTEM, MODEL_SYSTEM, PARAMETER_SYSTEM,
    PERSONA_SYSTEM, PRACTICE_SYSTEM, PRICING_SYSTEM, PROFILE_SYSTEM,
    PROVIDER_SYSTEM, RECORD_SYSTEM, REPORTS_SYSTEM, RUBRIC_SYSTEM,
    SCENARIO_SYSTEM, SESSION_SYSTEM, SETTING_SYSTEM, SIMULATION_SYSTEM,
    TEST_GRADE_SYSTEM, TEST_INSIGHT_SYSTEM, TOOL_SYSTEM,
]

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
        auth_ids=AUTH_RESOURCE_ID_LIST or None,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS or None,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS or None,
        provider_key_ids=PROVIDER_KEY_IDS or None,
        system_ids=ALL_SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        profile_ids=[FRESH_SUPERADMIN_RESOURCE],
    ),
]
