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
    email="superadmin@glow.local",
    role_id=SUPERADMIN_ROLE,
    flag_ids=[PROFILE_ACTIVE],
)

# The fresh setup has no departments, so agents stay global (empty list
# disables the department_ids injection). See university/__init__.py for
# the rationale behind this hook.
AGENT_DEPARTMENT_IDS: list = []

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "profiles",
    "logins",
    "colors",
    "settings",
]
