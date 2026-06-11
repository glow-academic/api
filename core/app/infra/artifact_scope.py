"""Shared department-scope clamp for artifact *search* (list) endpoints.

Every dept-scopable artifact's DETAIL ``get`` enforces an identical
``has_access`` predicate (super-admin global, dept-less artifacts shared,
otherwise department overlap) and 403s the caller when it fails. The LIST
(``search``) endpoints, however, historically computed the caller's
role/dept only for per-row ``can_edit``/``can_delete`` flags and then
appended *every* hydrated row unconditionally — leaking the metadata
(names, descriptions, content pointers, member rosters, …) of artifacts in
departments the caller could not open in detail.

``eval/search`` and ``cohort/search`` got a hand-written clamp for this
(issue: authz-scope leak); this module is the *class* fix: a single
predicate + filter applied uniformly across every dept-scopable artifact
search, so the same overlap test the detail path enforces is applied to the
list and the bug cannot regress per-artifact.

Exempt by design (NOT clamped here, intentionally):
  * ``tool`` — org-wide catalog; its detail ``has_access`` is role-only.
  * ``test`` — its detail ``get`` has no department gate to mirror.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID


def actor_can_access_departments(
    role_level: int,
    user_department_ids: Sequence[UUID] | None,
    artifact_department_ids: Sequence[UUID] | None,
) -> bool:
    """Mirror every artifact's per-artifact ``has_access`` dept predicate.

    Access rules (identical across all dept-scopable artifacts):
      * Level 0 (super-admin / top-level) sees everything.
      * An artifact with no departments is shared with everyone.
      * Otherwise the caller must share at least one department with it.
    """
    if role_level == 0:
        return True

    if not artifact_department_ids:
        return True

    if not user_department_ids:
        return False

    return bool(set(user_department_ids) & set(artifact_department_ids))


_T = TypeVar("_T")


def clamp_artifacts_to_actor_scope(
    artifacts: Sequence[_T],
    role_level: int,
    user_department_ids: Sequence[UUID] | None,
    total_count: int,
    *,
    department_attr: str = "department_ids",
) -> tuple[list[_T], int]:
    """Drop artifacts the actor cannot view; adjust ``total_count``.

    Mirrors the ``eval/search`` + ``cohort/search`` clamp exactly: filter the
    hydrated page by :func:`actor_can_access_departments` against each row's
    ``department_ids`` and decrement ``total_count`` by the rows removed on
    this page, so the count never advertises hidden artifacts.

    Returns ``(visible_artifacts, adjusted_total_count)``.
    """
    pre_clamp_count = len(artifacts)
    visible = [
        a
        for a in artifacts
        if actor_can_access_departments(
            role_level,
            user_department_ids,
            list(getattr(a, department_attr, None) or []),
        )
    ]
    adjusted = max(0, total_count - (pre_clamp_count - len(visible)))
    return visible, adjusted
