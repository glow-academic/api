"""Organization profile seed definitions — setup-specific, independent from base modules."""

from database.seeds.ids import sid
from database.seeds.profiles import (
    ADMIN_ROLE,
    GUEST_ROLE,
    GUEST_REQUEST_LIMIT,
    INSTRUCTIONAL_ROLE,
    MEMBER_GTA_ROLE,
    PROFILE_ACTIVE,
    SUPERADMIN_ROLE,
)
from database.seeds.setups.organization.departments import ORGANIZATION_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

ORG_SUPERADMIN = sid("org/profile/superadmin")
ORG_SUPERADMIN_RESOURCE = sid("org/profile-resource/superadmin")
ORG_ADMIN = sid("org/profile/admin")
ORG_ADMIN_RESOURCE = sid("org/profile-resource/admin")
ORG_INSTRUCTIONAL = sid("org/profile/instructional")
ORG_INSTRUCTIONAL_RESOURCE = sid("org/profile-resource/instructional")
ORG_MEMBER = sid("org/profile/member")
ORG_MEMBER_RESOURCE = sid("org/profile-resource/member")
ORG_GUEST = sid("org/profile/guest")
ORG_GUEST_RESOURCE = sid("org/profile-resource/guest")

# ---------------------------------------------------------------------------
# Setup-specific profiles (created as new artifacts, not updates to base profiles)
# ---------------------------------------------------------------------------

setup_profiles = [
    # Note: superadmin is bootstrapped by the runner, not created here.
    dict(
        id=ORG_ADMIN,
        resource_id=ORG_ADMIN_RESOURCE,
        name="Default Admin",
        email="default-admin@organization.com",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
        role_id=ADMIN_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=ORG_INSTRUCTIONAL,
        resource_id=ORG_INSTRUCTIONAL_RESOURCE,
        name="Default Instructional",
        email="default-instructional@organization.com",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
        role_id=INSTRUCTIONAL_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=ORG_MEMBER,
        resource_id=ORG_MEMBER_RESOURCE,
        name="Default Member",
        email="default-member@organization.com",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
        role_id=MEMBER_GTA_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
    dict(
        id=ORG_GUEST,
        resource_id=ORG_GUEST_RESOURCE,
        name="Default Guest",
        email="default-guest@organization.com",
        department_ids=[ORGANIZATION_DEPT_RESOURCE],
        role_id=GUEST_ROLE,
        active_flag_id=PROFILE_ACTIVE,
    ),
]
