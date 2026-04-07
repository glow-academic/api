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

Updates are applied automatically after all creates:
  - profiles.profile_updates → link pre-existing base profiles to department + email
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
    "colors",
    "settings",
    "texts",
    "files",
]
