"""Organization setup — seed definitions.

Dependency order (each module may reference IDs from earlier modules):
  1. departments
  2. personas       (refs: departments)
  3. fields         (refs: departments)
  4. parameters     (refs: fields, departments)
  5. keys           (refs: providers, auths, keys, items from base modules)
  6. settings       (refs: departments, auth, keys, systems, thresholds)
  7. profiles       (updates: pre-existing profiles → department + email)

Updates are applied automatically after all creates:
  - departments.get_department_updates() → link departments to settings
  - profiles.profile_updates → link pre-existing profiles to department
"""

SETUP_NAME = "organization"

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "departments",
    "personas",
    "fields",
    "parameters",
    "keys",
    "settings",
    "profiles",
]
