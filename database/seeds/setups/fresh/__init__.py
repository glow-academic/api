"""Fresh setup — minimal working deployment with no departments.

Creates the default setting and setup-specific profiles (superadmin, admin,
instructional, member, guest) with emails. No departments, no scenarios,
no simulations — just a working login screen.

All data is created at creation time — no update pass needed.
"""

SETUP_NAME = "fresh"

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "profiles",
    "settings",
]
