"""University setting seed definitions.

Each setting is a dict mapping directly to CreateSettingItem.
References pre-existing auth, system, and threshold resources from modules 01-10.

Names and descriptions are CREATED as new resources.
Provider keys and auth item keys are created by the keys module and linked here.
"""

from uuid import UUID

from database.seeds.auths import AUTH_RESOURCE_IDS
from database.seeds.ids import sid
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
# Profile resource IDs for setting linkage
# ---------------------------------------------------------------------------

SETTING_PROFILE_RESOURCE_IDS = [BENCHMARK_PROFILE_RESOURCE, UNI_SUPERADMIN_RESOURCE]

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs (from 01-resources/06-thresholds.sql)
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = UUID("019b995b-5308-7a8e-9d31-b08127742439")  # 85
THRESHOLD_WARNING = UUID("019b995b-5309-714f-a5f6-5614613257b1")  # 80
THRESHOLD_DANGER = UUID("019b995b-5309-74df-991a-c28980b294f2")  # 70

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
        auth_ids=list(AUTH_RESOURCE_IDS.values()),
        provider_key_ids=PROVIDER_KEY_IDS,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS,
        auth_item_value_ids=AUTH_ITEM_VALUE_IDS,
        system_ids=SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        color_ids=ALL_COLOR_IDS,
        profile_ids=SETTING_PROFILE_RESOURCE_IDS,
    ),
]
