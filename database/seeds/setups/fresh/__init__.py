"""Fresh setup — minimal working deployment with no departments.

Creates the default setting and setup-specific profiles (superadmin, admin,
instructional, member, guest) with emails. No departments, no scenarios,
no simulations — just a working login screen.

All data is created at creation time — no update pass needed.
"""

SETUP_NAME = "fresh"

from database.seeds.setups.fresh.profiles import FRESH_SUPERADMIN, FRESH_SUPERADMIN_RESOURCE
from database.seeds.profiles import SUPERADMIN_ROLE, PROFILE_ACTIVE

BOOTSTRAP_PROFILE = dict(
    id=FRESH_SUPERADMIN,
    resource_id=FRESH_SUPERADMIN_RESOURCE,
    name="Default Superadmin",
    role_ids=[SUPERADMIN_ROLE],
    flag_ids=[PROFILE_ACTIVE],
)

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "profiles",
    "settings",
]
