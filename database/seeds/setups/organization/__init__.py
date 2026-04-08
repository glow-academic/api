"""Organization setup — seed definitions.

Dependency order (each module may reference IDs from earlier modules):
  1. departments
  2. personas       (refs: departments)
  3. fields         (refs: departments)
  4. parameters     (refs: fields, departments)
  5. keys           (refs: providers, auths, keys, items from base modules)
  6. settings       (refs: departments, auth, keys, systems, thresholds)
  7. profiles       (updates: pre-existing profiles → department + email)

All data is created at creation time — no update pass needed.
"""

SETUP_NAME = "organization"

from database.seeds.setups.organization.departments import ORGANIZATION_DEPT_RESOURCE
from database.seeds.setups.organization.profiles import ORG_SUPERADMIN, ORG_SUPERADMIN_RESOURCE
from database.seeds.profiles import SUPERADMIN_ROLE, PROFILE_ACTIVE

BOOTSTRAP_PROFILE = dict(
    id=ORG_SUPERADMIN,
    resource_id=ORG_SUPERADMIN_RESOURCE,
    name="Default Superadmin",
    email="default-superadmin@organization.com",
    department_ids=[ORGANIZATION_DEPT_RESOURCE],
    role_ids=[SUPERADMIN_ROLE],
    flag_ids=[PROFILE_ACTIVE],
)

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "departments",
    "personas",
    "fields",
    "parameters",
    "settings",
    "profiles",
]
