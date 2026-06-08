"""University department seed definitions.

Each department is a dict mapping directly to CreateDepartmentItem.
Names and descriptions are CREATED as new resources.

settings_ids uses a forward-reference to the setting resource ID (no FK constraint
on department_settings_junction, so the setting doesn't need to exist yet).
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules for department_ids linking
# ---------------------------------------------------------------------------

UNIVERSITY_DEPT = sid("uni/department/university")
UNIVERSITY_DEPT_RESOURCE = sid("uni/department-resource/university")

# ---------------------------------------------------------------------------
# Additional academic departments — realistic university faculties.
#
# Why 14 total: the department list view paginates at 12 rows/page, so a
# single seeded department leaves the list a one-row demo with no second
# page to show. Seeding 14 (University + 13 below) gives a populated first
# page AND a second page, unblocking the department list/pagination demos.
#
# Each extra department links to the canonical University setting via
# ``settings_ids`` (forward-reference — there's no FK on
# department_settings_junction, so the setting resource needn't exist yet).
# The four department-scoped settings seeded in settings.py also target a
# subset of these so the settings library demo shows real per-department rows.
# ---------------------------------------------------------------------------

# (slug, display name, description) — slug drives the deterministic sid keys.
_EXTRA_DEPARTMENTS: list[tuple[str, str, str]] = [
    ("computer-science", "Computer Science", "Algorithms, systems, and the theory and practice of computation."),
    ("mathematics", "Mathematics", "Pure and applied mathematics, from analysis to discrete structures."),
    ("biology", "Biology", "The study of living systems, from molecules to ecosystems."),
    ("history", "History", "Human societies, events, and ideas across time and place."),
    ("physics", "Physics", "Matter, energy, and the fundamental laws governing the universe."),
    ("chemistry", "Chemistry", "Composition, structure, and transformation of matter."),
    ("english", "English", "Literature, composition, rhetoric, and critical reading."),
    ("psychology", "Psychology", "Mind and behavior across cognition, development, and society."),
    ("economics", "Economics", "Markets, incentives, and the allocation of scarce resources."),
    ("mechanical-engineering", "Mechanical Engineering", "Design and analysis of mechanical and thermal systems."),
    ("political-science", "Political Science", "Government, institutions, policy, and political behavior."),
    ("philosophy", "Philosophy", "Logic, ethics, metaphysics, and the foundations of knowledge."),
    ("nursing", "Nursing", "Evidence-based patient care, health promotion, and clinical practice."),
]

# Deterministic resource IDs for the extra departments, keyed by slug — so
# cohorts.py and settings.py can reference them without re-deriving the sid.
EXTRA_DEPT_RESOURCES: dict[str, "object"] = {
    slug: sid(f"uni/department-resource/{slug}") for slug, _name, _desc in _EXTRA_DEPARTMENTS
}

# ---------------------------------------------------------------------------
# Department definitions (creates)
# ---------------------------------------------------------------------------

departments = [
    dict(
        id=UNIVERSITY_DEPT,
        resource_id=UNIVERSITY_DEPT_RESOURCE,
        name="University",
        description="Innovative base of knowledge in the emerging field of computing.",
        settings_ids=[sid("uni/setting-resource/university")],
    ),
] + [
    dict(
        id=sid(f"uni/department/{slug}"),
        resource_id=sid(f"uni/department-resource/{slug}"),
        name=name,
        description=desc,
        settings_ids=[sid("uni/setting-resource/university")],
    )
    for slug, name, desc in _EXTRA_DEPARTMENTS
]
