"""University setting seed definitions.

Each setting is a dict mapping directly to CreateSettingItem.
References pre-existing auth, system, and threshold resources from modules 01-10.

Names and descriptions are CREATED as new resources.
Provider keys and auth item keys are created by the keys module and linked here.
"""

from database.seeds.ids import sid
from database.seeds.logins import (
    AUTH_LOGIN_IDS,
    build_profile_logins,
)
from database.seeds.mcps import MCP_COMPOSER
from database.seeds.setups.university.departments import (
    UNIVERSITY_DEPT,
    UNIVERSITY_DEPT_RESOURCE,
)
from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
    PROVIDER_KEY_IDS,
)
from database.seeds.setting import ALL_SYSTEMS
from database.seeds.setups.university.colors import ALL_COLOR_IDS
from database.seeds.setups.university.profiles import (
    BENCHMARK_PROFILE_RESOURCE,
    UNI_SUPERADMIN_RESOURCE,
)

# ---------------------------------------------------------------------------
# Logins — auth logins from config + profile logins from linked profiles
# ---------------------------------------------------------------------------

_PROFILE_LOGINS = build_profile_logins([
    dict(name="Benchmark", resource_id=BENCHMARK_PROFILE_RESOURCE),
    dict(name="Default Superadmin", resource_id=UNI_SUPERADMIN_RESOURCE),
])
UNI_LOGINS_IDS = AUTH_LOGIN_IDS + [lg["id"] for lg in _PROFILE_LOGINS]
UNI_LOGINS = _PROFILE_LOGINS  # auth logins are in AUTH_LOGINS (logins.py)

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs (from 01-resources/06-thresholds.sql)
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

# ---------------------------------------------------------------------------
# Pre-existing system resource IDs (from 10-systems/)
# ---------------------------------------------------------------------------

SYSTEMS = ALL_SYSTEMS

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

UNIVERSITY_SETTING = sid("uni/setting/university")
UNIVERSITY_SETTING_RESOURCE = sid("uni/setting-resource/university")

# ---------------------------------------------------------------------------
# Setting definitions
# ---------------------------------------------------------------------------

settings = [
    dict(
        id=UNIVERSITY_SETTING,
        resource_id=UNIVERSITY_SETTING_RESOURCE,
        name="University Settings",
        description="Department-specific settings for the University, linking authentication, AI systems, and grading thresholds.",
        active_flag=True,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        provider_key_ids=PROVIDER_KEY_IDS,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS,
        system_ids=SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        color_ids=ALL_COLOR_IDS,
        logins_ids=UNI_LOGINS_IDS or None,
        mcp_id=MCP_COMPOSER,
    ),
]
