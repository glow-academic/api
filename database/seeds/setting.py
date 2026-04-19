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
    AUTH_RESOURCE_ID_LIST,
)
from database.seeds.profiles import SEED_PROFILE_RESOURCE
from database.seeds.agents import (
    AGENT_AGENT_RESOURCE,
    ATTEMPT_AGENT_RESOURCE,
    AUTH_AGENT_RESOURCE,
    CHAT_AGENT_RESOURCE,
    COHORT_AGENT_RESOURCE,
    COMPOSER_AGENT_RESOURCE,
    DEPARTMENT_AGENT_RESOURCE,
    DOCUMENT_AGENT_RESOURCE,
    EVAL_AGENT_RESOURCE,
    FIELD_AGENT_RESOURCE,
    GROUP_AGENT_RESOURCE,
    INVOCATION_AGENT_RESOURCE,
    MODEL_AGENT_RESOURCE,
    PARAMETER_AGENT_RESOURCE,
    PERSONA_AGENT_RESOURCE,
    PROFILE_AGENT_RESOURCE,
    PROVIDER_AGENT_RESOURCE,
    RUBRIC_AGENT_RESOURCE,
    SCENARIO_AGENT_RESOURCE,
    SCENARIO_IMAGE_AGENT_RESOURCE,
    SCENARIO_VIDEO_AGENT_RESOURCE,
    SETTING_AGENT_RESOURCE,
    SIMULATION_AGENT_RESOURCE,
    TEST_GRADE_AGENT_RESOURCE,
    TOOL_AGENT_RESOURCE,
)

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs (from module 01 resources)
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

# ---------------------------------------------------------------------------
# All agent IDs (flattened from former system → agent mapping)
# ---------------------------------------------------------------------------

ALL_AGENTS = [
    # CRUD artifact agents (create, update, delete, generate)
    AGENT_AGENT_RESOURCE,
    AUTH_AGENT_RESOURCE,
    CHAT_AGENT_RESOURCE,
    COHORT_AGENT_RESOURCE,
    DEPARTMENT_AGENT_RESOURCE,
    DOCUMENT_AGENT_RESOURCE,
    EVAL_AGENT_RESOURCE,
    FIELD_AGENT_RESOURCE,
    MODEL_AGENT_RESOURCE,
    PARAMETER_AGENT_RESOURCE,
    PERSONA_AGENT_RESOURCE,
    PROFILE_AGENT_RESOURCE,
    PROVIDER_AGENT_RESOURCE,
    RUBRIC_AGENT_RESOURCE,
    SCENARIO_AGENT_RESOURCE,
    SCENARIO_IMAGE_AGENT_RESOURCE,
    SCENARIO_VIDEO_AGENT_RESOURCE,
    SETTING_AGENT_RESOURCE,
    SIMULATION_AGENT_RESOURCE,
    TOOL_AGENT_RESOURCE,
    # Attempt + test agents
    ATTEMPT_AGENT_RESOURCE,
    TEST_GRADE_AGENT_RESOURCE,
    # Orchestration
    COMPOSER_AGENT_RESOURCE,
    GROUP_AGENT_RESOURCE,
    INVOCATION_AGENT_RESOURCE,
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
        agent_ids=ALL_AGENTS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        profile_ids=DEFAULT_PROFILE_RESOURCE_IDS,
    ),
]


