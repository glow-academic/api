"""University profile-persona seed definitions.

Maps each profile to the Student persona — the AI sees every user as a student
during simulations. Each entry creates a profile_personas_resource row.
"""

from database.seeds.ids import sid
from database.seeds.setups.university.personas import STUDENT_RESOURCE
from database.seeds.setups.university.profiles import (
    PROFESSOR_SMITH_RESOURCE,
    TA_JOHNSON_RESOURCE,
    UNI_ADMIN_RESOURCE,
    UNI_GUEST_RESOURCE,
    UNI_INSTRUCTIONAL_RESOURCE,
    UNI_MEMBER_RESOURCE,
    UNI_SUPERADMIN_RESOURCE,
    UNIVERSITY_ADMIN_RESOURCE,
)

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by cohorts
# ---------------------------------------------------------------------------

PP_SUPERADMIN = sid("uni/profile-persona/superadmin+student")
PP_UNIVERSITY_ADMIN = sid("uni/profile-persona/university-admin+student")
PP_PROFESSOR_SMITH = sid("uni/profile-persona/professor-smith+student")
PP_TA_JOHNSON = sid("uni/profile-persona/ta-johnson+student")
PP_ADMIN = sid("uni/profile-persona/admin+student")
PP_INSTRUCTIONAL = sid("uni/profile-persona/instructional+student")
PP_MEMBER = sid("uni/profile-persona/member+student")
PP_GUEST = sid("uni/profile-persona/guest+student")

# ---------------------------------------------------------------------------
# Profile-persona definitions
# ---------------------------------------------------------------------------

profile_personas = [
    dict(id=PP_SUPERADMIN, profile_id=UNI_SUPERADMIN_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_UNIVERSITY_ADMIN, profile_id=UNIVERSITY_ADMIN_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_PROFESSOR_SMITH, profile_id=PROFESSOR_SMITH_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_TA_JOHNSON, profile_id=TA_JOHNSON_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_ADMIN, profile_id=UNI_ADMIN_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_INSTRUCTIONAL, profile_id=UNI_INSTRUCTIONAL_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_MEMBER, profile_id=UNI_MEMBER_RESOURCE, persona_id=STUDENT_RESOURCE),
    dict(id=PP_GUEST, profile_id=UNI_GUEST_RESOURCE, persona_id=STUDENT_RESOURCE),
]

# All profile-persona IDs (for cohort definitions)
ALL_PROFILE_PERSONA_IDS = [
    PP_SUPERADMIN,
    PP_UNIVERSITY_ADMIN,
    PP_PROFESSOR_SMITH,
    PP_TA_JOHNSON,
    PP_ADMIN,
    PP_INSTRUCTIONAL,
    PP_MEMBER,
    PP_GUEST,
]
