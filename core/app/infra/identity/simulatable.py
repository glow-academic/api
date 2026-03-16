"""Role hierarchy constants for emulation and profile visibility."""

# Role hierarchy: who can emulate whom (excludes self-role for non-superadmins)
SIMULATABLE_ROLES: dict[str, set[str]] = {
    "superadmin": {"superadmin", "admin", "instructional", "member", "guest"},
    "admin": {"instructional", "member", "guest"},
    "instructional": {"member", "guest"},
}
