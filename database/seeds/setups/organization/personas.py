"""Organization persona seed definitions.

Minimal personas — name only, no descriptions/instructions.
"""

from database.seeds.ids import sid
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT

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
        name="Frustrated",
        color="Red",
        icon="Zap",
        instructions="You are frustrated.",
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=ANXIOUS,
        name="Anxious",
        color="Amber",
        icon="HelpCircle",
        instructions="You are anxious.",
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=DEFENSIVE,
        name="Defensive",
        color="Violet",
        icon="Cloud",
        instructions="You are defensive.",
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=ENTHUSIASTIC,
        name="Enthusiastic",
        color="Green",
        icon="SmilePlus",
        instructions="You are enthusiastic.",
        department_ids=[ORGANIZATION_DEPT],
    ),
    dict(
        id=MANAGER,
        name="Manager",
        color="Blue",
        icon="User",
        instructions="You are a manager.",
        department_ids=[ORGANIZATION_DEPT],
    ),
]
