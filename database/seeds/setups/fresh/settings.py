"""Fresh setting seed — platform default with no departments.

Creates a setting with all agents enabled, default thresholds,
auth providers, and the fresh superadmin profile linked.
This gives a working login screen out of the box.
"""

from database.seeds.dynamic_keys import (
    AUTH_ITEM_KEY_IDS,
    AUTH_ITEM_VALUE_IDS,
    AUTH_RESOURCE_ID_LIST,
    PROVIDER_KEY_IDS,
)
from database.seeds.ids import sid
from database.seeds.setups.fresh.profiles import FRESH_SUPERADMIN_RESOURCE
from database.seeds.setting import ALL_AGENTS

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLD_SUCCESS = sid("threshold/85")
THRESHOLD_WARNING = sid("threshold/80")
THRESHOLD_DANGER = sid("threshold/70")

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
        agent_ids=ALL_AGENTS,
        threshold_ids=[THRESHOLD_SUCCESS, THRESHOLD_WARNING, THRESHOLD_DANGER],
        profile_ids=[FRESH_SUPERADMIN_RESOURCE],
    ),
]
