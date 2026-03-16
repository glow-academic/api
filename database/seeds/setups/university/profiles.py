"""University profile seed definitions.

Each profile is a dict of primitives that maps directly to CreateProfileItem.
The `id` field is a deterministic UUID so downstream seeds can reference these
profiles by importing the ID constants.

Names are CREATED as new resources.
Role and department IDs reference pre-existing resources (01-resources/).
"""

from uuid import UUID

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT

# ---------------------------------------------------------------------------
# Pre-existing role resource IDs (from database/seeds/resources/roles.py)
# ---------------------------------------------------------------------------

ROLE_ADMIN = UUID("019bbabc-5a36-76d3-8fc3-8415fe308cd3")
ROLE_INSTRUCTIONAL = UUID("019bbabc-5a3b-741e-bad3-474cc6c05fd6")
ROLE_BENCHMARK = UUID("019bdb94-b279-70c0-a610-6b9696fb5c94")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

UNIVERSITY_ADMIN = sid("uni/profile/university-admin")
PROFESSOR_SMITH = sid("uni/profile/professor-smith")
TA_JOHNSON = sid("uni/profile/ta-johnson")
BENCHMARK_PROFILE = sid("uni/profile/benchmark")

# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

profiles = [
    # ── University Admin ─────────────────────────────────────────────────
    dict(
        id=UNIVERSITY_ADMIN,
        name="University Admin",
        department_ids=[UNIVERSITY_DEPT],
        role_ids=[ROLE_ADMIN],
    ),
    # ── Professor Smith ──────────────────────────────────────────────────
    dict(
        id=PROFESSOR_SMITH,
        name="Professor Smith",
        department_ids=[UNIVERSITY_DEPT],
        role_ids=[ROLE_INSTRUCTIONAL],
    ),
    # ── TA Johnson ───────────────────────────────────────────────────────
    dict(
        id=TA_JOHNSON,
        name="TA Johnson",
        department_ids=[UNIVERSITY_DEPT],
        role_ids=[ROLE_INSTRUCTIONAL],
    ),
    # ── Benchmark ──────────────────────────────────────────────────────
    dict(
        id=BENCHMARK_PROFILE,
        name="Benchmark",
        department_ids=[UNIVERSITY_DEPT],
        role_ids=[ROLE_BENCHMARK],
    ),
]

# ---------------------------------------------------------------------------
# Pre-existing profile IDs (from 09-profiles in modules 01-10)
# ---------------------------------------------------------------------------

DEFAULT_ADMIN = UUID("019b3be4-36ef-7a5f-98ab-ccb879770be0")
DEFAULT_GUEST = UUID("019b3be4-36f0-792c-82d6-126664ed18b6")
DEFAULT_INSTRUCTIONAL = UUID("019b3be4-36f0-785d-9d61-32eae65689ca")
DEFAULT_MEMBER = UUID("019b3be4-36f0-7eb3-bc4e-bcab772edd92")
DEFAULT_SUPERADMIN = UUID("019b3be4-36f0-788c-9df2-481eb5917940")

# ---------------------------------------------------------------------------
# Profile updates — link pre-existing profiles to this setup's department
# ---------------------------------------------------------------------------

profile_updates = [
    dict(
        profile_id=DEFAULT_ADMIN,
        department_ids=[UNIVERSITY_DEPT],
        email="default-admin@university.edu",
    ),
    dict(
        profile_id=DEFAULT_GUEST,
        department_ids=[UNIVERSITY_DEPT],
        email="default-guest@university.edu",
    ),
    dict(
        profile_id=DEFAULT_INSTRUCTIONAL,
        department_ids=[UNIVERSITY_DEPT],
        email="default-instructional@university.edu",
    ),
    dict(
        profile_id=DEFAULT_MEMBER,
        department_ids=[UNIVERSITY_DEPT],
        email="default-member@university.edu",
    ),
    dict(
        profile_id=DEFAULT_SUPERADMIN,
        department_ids=[UNIVERSITY_DEPT],
        email="default-superadmin@university.edu",
    ),
]
