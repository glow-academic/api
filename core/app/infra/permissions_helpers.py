"""Shared permission helpers for RBAC checks.

Fully generic — no knowledge of specific role names.
All checks use two mechanisms:
  1. Permission set: (artifact, operation) tuples from role's permission_ids
  2. Role level: integer hierarchy (0 = highest privilege)
"""


def has_permission(
    role_permissions: list[tuple[str, str]] | set[tuple[str, str]],
    artifact: str,
    operation: str,
) -> bool:
    """Check if the role has a specific (artifact, operation) permission."""
    return (artifact, operation) in role_permissions


def can_manage_level(user_level: int, target_level: int) -> bool:
    """Check if user level is strictly above target (lower number = higher privilege)."""
    return user_level < target_level
