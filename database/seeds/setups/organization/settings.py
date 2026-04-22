"""Organization setting seed definitions.

References pre-existing auth, system, and threshold resources from modules 01-10.
Provider keys and auth item keys are created by the keys module and linked here.
"""

from database.seeds.ids import sid
from database.seeds.logins import AUTH_LOGIN_IDS
from database.seeds.setups.organization.departments import (
    ORGANIZATION_DEPT,
    ORGANIZATION_DEPT_RESOURCE,
)
from database.seeds.dynamic_keys import AUTH_ITEM_KEY_IDS, PROVIDER_KEY_IDS
from database.seeds.setting import ALL_SYSTEMS

# ---------------------------------------------------------------------------
# Pre-existing threshold resource IDs
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

# ---------------------------------------------------------------------------
# Pre-existing flag IDs
# ---------------------------------------------------------------------------

FLAG_ACTIVE = sid("flag/setting-active")
FLAG_PRACTICE = sid("flag/practice")
FLAG_SCORING = sid("flag/scoring")

# ---------------------------------------------------------------------------
# System IDs
# ---------------------------------------------------------------------------

SYSTEMS = ALL_SYSTEMS

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ORGANIZATION_SETTING = sid("org/setting/organization")
ORGANIZATION_SETTING_RESOURCE = sid("org/setting-resource/organization")

# ---------------------------------------------------------------------------
# Setting definitions
# ---------------------------------------------------------------------------

settings = [
    dict(
        id=ORGANIZATION_SETTING,
        resource_id=ORGANIZATION_SETTING_RESOURCE,
        name="Organization Settings",
        description="Settings for the Organization department",
        active_flag=True,
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
        provider_key_ids=PROVIDER_KEY_IDS,
        auth_item_key_ids=AUTH_ITEM_KEY_IDS,
        system_ids=SYSTEMS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        logins_ids=AUTH_LOGIN_IDS or None,
    ),
]
