"""Organization persona seed definitions.

Minimal personas — name only, no descriptions/instructions.
"""

from database.seeds.ids import sid
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT, ORGANIZATION_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

FRUSTRATED = sid("org/persona/frustrated")
ANXIOUS = sid("org/persona/anxious")
DEFENSIVE = sid("org/persona/defensive")
ENTHUSIASTIC = sid("org/persona/enthusiastic")
MANAGER = sid("org/persona/manager")

# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

personas = [
    dict(
        id=FRUSTRATED,
        resource_id=sid("org/persona-resource/frustrated"),
        name="Frustrated",
        color="Red",
        icon="Zap",
        instructions="You are frustrated.",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=ANXIOUS,
        resource_id=sid("org/persona-resource/anxious"),
        name="Anxious",
        color="Amber",
        icon="HelpCircle",
        instructions="You are anxious.",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=DEFENSIVE,
        resource_id=sid("org/persona-resource/defensive"),
        name="Defensive",
        color="Violet",
        icon="Cloud",
        instructions="You are defensive.",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=ENTHUSIASTIC,
        resource_id=sid("org/persona-resource/enthusiastic"),
        name="Enthusiastic",
        color="Green",
        icon="SmilePlus",
        instructions="You are enthusiastic.",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
    dict(
        id=MANAGER,
        resource_id=sid("org/persona-resource/manager"),
        name="Manager",
        color="Blue",
        icon="User",
        instructions="You are a manager.",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
    ),
]
