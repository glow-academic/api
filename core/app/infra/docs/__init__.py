"""Shared docs types and helpers.

Re-exports common types so callers can `from app.infra.docs import X`
in addition to the direct `from app.infra.docs.types import X`.
"""

from app.infra.docs.types import (
    CallerPermissions,
    ColumnInfo,
    ComposedContextResponse,
    ComposedDocsResponse,
    DocsResponse,
    MvInfo,
    OperationInfo,
    OperationPrompts,
    ParamInfo,
    ProfileSummary,
    StarterPrompt,
    TableInfo,
)

__all__ = [
    "CallerPermissions",
    "ColumnInfo",
    "ComposedContextResponse",
    "ComposedDocsResponse",
    "DocsResponse",
    "MvInfo",
    "OperationInfo",
    "OperationPrompts",
    "ParamInfo",
    "ProfileSummary",
    "StarterPrompt",
    "TableInfo",
]
