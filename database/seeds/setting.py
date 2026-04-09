"""Default setting — baked into fresh.sql.gz.

Creates a setting with no department attached, all systems enabled,
default thresholds, and the default superadmin profile linked.
Auth providers are dynamically included from glow-deploy.yaml config.
This gives a working login screen out of the box on fresh deploys.
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
    AUTH_RESOURCE_ID_LIST,
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

THRESHOLD_SUCCESS = UUID("019b995b-5308-7a8e-9d31-b08127742439")  # 85
THRESHOLD_WARNING = UUID("019b995b-5309-714f-a5f6-5614613257b1")  # 80
THRESHOLD_DANGER = UUID("019b995b-5309-74df-991a-c28980b294f2")  # 70

# ---------------------------------------------------------------------------
# All system IDs
# ---------------------------------------------------------------------------

ALL_SYSTEMS = [
    ACTIVITY_SYSTEM,
    AGENT_SYSTEM,
    ATTEMPT_CHAT_SYSTEM,
    ATTEMPT_GRADE_SYSTEM,
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
    TOOL_SYSTEM,
    COMPOSER_SYSTEM,
]

# ---------------------------------------------------------------------------
# Default profile artifact IDs to link (for "Login as X" on Keycloak)
# ---------------------------------------------------------------------------

DEFAULT_PROFILE_RESOURCE_IDS = [SEED_PROFILE_RESOURCE]

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
        auth_ids=AUTH_RESOURCE_ID_LIST or None,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS or None,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS or None,
        system_ids=ALL_SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        profile_ids=DEFAULT_PROFILE_RESOURCE_IDS,
    ),
]


