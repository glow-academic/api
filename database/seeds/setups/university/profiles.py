"""University profile seed definitions.

Each profile is a dict of primitives that maps directly to CreateProfileItem.
The `id` field is a deterministic UUID so downstream seeds can reference these
profiles by importing the ID constants.

Names are CREATED as new resources.
Role and department IDs reference pre-existing resources (01-resources/).
"""

from database.seeds.ids import sid
from database.seeds.profiles import (
    ADMIN_ROLE,
    GUEST_ROLE,
    GUEST_REQUEST_LIMIT,
    INSTRUCTIONAL_ROLE,
    MEMBER_GTA_ROLE,
    MEMBER_UTA_ROLE,
    PROFILE_ACTIVE,
    SUPERADMIN_ROLE,
)
from database.seeds.setups.university.departments import UNIVERSITY_DEPT, UNIVERSITY_DEPT_RESOURCE

BENCHMARK_ROLE = sid("role/benchmark")

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

UNIVERSITY_ADMIN = sid("uni/profile/university-admin")
PROFESSOR_SMITH = sid("uni/profile/professor-smith")
TA_JOHNSON = sid("uni/profile/ta-johnson")
BENCHMARK_PROFILE = sid("uni/profile/benchmark")

UNIVERSITY_ADMIN_RESOURCE = sid("uni/profile-resource/university-admin")
PROFESSOR_SMITH_RESOURCE = sid("uni/profile-resource/professor-smith")
TA_JOHNSON_RESOURCE = sid("uni/profile-resource/ta-johnson")
BENCHMARK_PROFILE_RESOURCE = sid("uni/profile-resource/benchmark")

# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

profiles = [
    # ── University Admin ─────────────────────────────────────────────────
    dict(
        id=UNIVERSITY_ADMIN,
        resource_id=UNIVERSITY_ADMIN_RESOURCE,
        name="University Admin",
        email="university-admin@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=ADMIN_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    # ── Professor Smith ──────────────────────────────────────────────────
    dict(
        id=PROFESSOR_SMITH,
        resource_id=PROFESSOR_SMITH_RESOURCE,
        name="Professor Smith",
        email="professor-smith@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=INSTRUCTIONAL_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    # ── TA Johnson ───────────────────────────────────────────────────────
    dict(
        id=TA_JOHNSON,
        resource_id=TA_JOHNSON_RESOURCE,
        name="TA Johnson",
        email="ta-johnson@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=MEMBER_UTA_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    # ── Benchmark ──────────────────────────────────────────────────────
    dict(
        id=BENCHMARK_PROFILE,
        resource_id=BENCHMARK_PROFILE_RESOURCE,
        name="Benchmark",
        email="benchmark@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=BENCHMARK_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
]

# ---------------------------------------------------------------------------
# Setup-specific versions of base profiles (independent from base modules)
# ---------------------------------------------------------------------------

UNI_SUPERADMIN = sid("uni/profile/superadmin")
UNI_SUPERADMIN_RESOURCE = sid("uni/profile-resource/superadmin")
UNI_ADMIN = sid("uni/profile/admin")
UNI_ADMIN_RESOURCE = sid("uni/profile-resource/admin")
UNI_INSTRUCTIONAL = sid("uni/profile/instructional")
UNI_INSTRUCTIONAL_RESOURCE = sid("uni/profile-resource/instructional")
UNI_MEMBER = sid("uni/profile/member")
UNI_MEMBER_RESOURCE = sid("uni/profile-resource/member")
UNI_GUEST = sid("uni/profile/guest")
UNI_GUEST_RESOURCE = sid("uni/profile-resource/guest")

# These are setup-specific profiles — created as new artifacts, not updates to base profiles
setup_profiles = [
    # Note: superadmin is bootstrapped by the runner, not created here.
    dict(
        id=UNI_ADMIN,
        resource_id=UNI_ADMIN_RESOURCE,
        name="Default Admin",
        email="default-admin@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=ADMIN_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=UNI_INSTRUCTIONAL,
        resource_id=UNI_INSTRUCTIONAL_RESOURCE,
        name="Default Instructional",
        email="default-instructional@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=INSTRUCTIONAL_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=UNI_MEMBER,
        resource_id=UNI_MEMBER_RESOURCE,
        name="Default Member",
        email="default-member@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=MEMBER_GTA_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=UNI_GUEST,
        resource_id=UNI_GUEST_RESOURCE,
        name="Default Guest",
        email="default-guest@university.edu",
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
        role_id=GUEST_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
]
