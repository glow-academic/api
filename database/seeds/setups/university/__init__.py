"""University setup — seed definitions.

Dependency order (each module may reference IDs from earlier modules):
  1. departments
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
  14. settings      (refs: departments, auth, keys, providers, systems)
  15. colors        (standalone color resources)
  16. texts         (refs: documents — text upload chain + document link)
  17. files         (refs: documents — file upload chain + document link)

Updates are applied automatically after all creates:
  - departments.get_department_updates() → link departments to settings
  - settings.get_setting_updates() → link settings to colors
  - profiles.profile_updates → link pre-existing profiles to department
"""

SETUP_NAME = "university"

# Dependency-ordered list of module names to seed.
# Each corresponds to a .py file in this package.
MODULES = [
    "departments",
    "documents",
    "personas",
    "rubrics",
    "fields",
    "parameters",
    "content",
    "scenarios",
    "scenario_rubrics",
    "simulations",
    "profiles",
    "cohorts",
    "keys",
    "settings",
    "colors",
    "texts",
    "files",
]
