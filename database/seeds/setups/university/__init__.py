"""University setup — seed definitions.

Dependency order (each module may reference IDs from earlier modules):
  1. departments    (refs: settings_ids=[SR] — no FK, forward-reference OK)
  2. documents
  3. personas
  4. rubrics
  5. fields         (standalone field values)
  6. parameters     (refs: fields)
  7. content        (objectives, questions, options — standalone resources)
  8. scenarios      (refs: personas, documents, content)
  9. scenario_rubrics (refs: scenarios, rubrics)
  10. simulations   (refs: scenarios, scenario_rubrics)
  11. profiles      (refs: departments; updates: pre-existing profiles → department + email)
  12. cohorts       (refs: simulations, profiles)
  13. keys          (refs: providers, auths, keys, items from base modules)
  14. colors        (standalone color resources — before settings so they can be included)
  15. settings      (refs: departments, auth, keys, providers, systems, colors, profiles)
  16. texts         (refs: documents — text upload chain + document link)
  17. files         (refs: documents — file upload chain + document link)

All data is created at creation time — no update pass needed.
"""

SETUP_NAME = "university"

from database.seeds.setups.university.departments import UNIVERSITY_DEPT_RESOURCE
from database.seeds.setups.university.profiles import UNI_SUPERADMIN, UNI_SUPERADMIN_RESOURCE
from database.seeds.profiles import SUPERADMIN_ROLE, PROFILE_ACTIVE

BOOTSTRAP_PROFILE = dict(
    id=UNI_SUPERADMIN,
    resource_id=UNI_SUPERADMIN_RESOURCE,
    name="Default Superadmin",
    email="default-superadmin@university.edu",
    department_ids=[UNIVERSITY_DEPT_RESOURCE],
    role_id=SUPERADMIN_ROLE,
    flag_ids=[PROFILE_ACTIVE],
)

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "departments",
    "documents",
    "personas",
    "rubrics",
    "fields",
    "parameters",
    "parameter_fields",
    "conditional_parameters",
    "content",
    "scenarios",
    "scenario_rubrics",
    "simulations",
    "profiles",
    "profile_personas",
    "cohorts",
    "colors",
    "settings",
    "texts",
    "files",
]
