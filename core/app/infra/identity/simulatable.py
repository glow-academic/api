"""Role hierarchy constants for emulation and profile visibility.

Keys and values use the canonical role names from the roles_resource table
(e.g. "Super Administrator", not the old short names like "superadmin").
"""

# Role hierarchy: who can emulate whom (excludes self-role for non-superadmins)
SIMULATABLE_ROLES: dict[str, set[str]] = {
    "Super Administrator": {
        "Super Administrator",
        "Administrator",
        "Instructional Staff",
        "GTA",
        "UTA",
        "Guest",
        "Benchmark",
    },
    "Administrator": {"Instructional Staff", "GTA", "UTA", "Guest"},
    "Instructional Staff": {"GTA", "UTA", "Guest"},
}
