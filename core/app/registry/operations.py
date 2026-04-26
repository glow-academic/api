"""Flat operation registry: (name, op) → (module, func) or None.

INFRA_OPS is auto-discovered from the filesystem (app/infra/{artifact}/{operation}.py).
INFRA_ITEM_TYPES is auto-discovered from Pydantic item classes in types.py files.

Manual overrides handle non-canonical mappings (cross-artifact refs, aliases).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


# ---------------------------------------------------------------------------
# Operation classification: READ vs WRITE
#
# WRITE operations mutate state and need ack during generation (soft path).
# READ operations are safe to execute immediately.
# ---------------------------------------------------------------------------

WRITE_OPERATIONS: frozenset[str] = frozenset({
    # CRUD
    "create", "update", "delete", "duplicate", "draft", "refresh",
    # Uploads
    "image_upload", "video_upload", "text_upload", "file_upload", "audio_upload",
    # Artifact-specific
    "run", "generate", "problem", "resolve", "emulate", "unemulate",
    "context", "name", "group", "feedback",
    # State machine
    "start", "next", "end", "end_all", "message", "grade", "stop", "complete",
    "response", "previous", "archive",
    "audio_start", "audio_frame", "audio_stop", "audio_mute",
})


def is_write_operation(operation: str) -> bool:
    """Check if an operation mutates state (needs ack during generation)."""
    return operation in WRITE_OPERATIONS


def resolve_callable(
    name: str,
    operation: str,
    ops: dict[tuple[str, str], tuple[str, str] | None],
) -> Callable[..., Any] | None:
    """Look up (name, operation) in an OPS dict and return the imported callable.

    Returns ``None`` if the entry is missing or maps to ``None`` (unimplemented).
    """
    entry = ops.get((name, operation))
    if entry is None:
        return None
    module_path, func_name = entry
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# INFRA_OPS — auto-discovered from filesystem + manual overrides
#
# Convention: app/infra/{artifact}/{operation}.py → *_impl function
# Auto-discovery finds all single-_impl files under app/infra/.
#
# Manual overrides handle:
#   - Attempt chat_* aliases (multiple operations → same impl)
#   - Cross-artifact refs (attempt.chat_get → chat.get)
#   - Test grade/feedback (non-standard function names)
# ---------------------------------------------------------------------------

_I = "app.infra"

from app.registry.discover import discover_infra_ops as _discover

# Auto-discover from filesystem
INFRA_OPS: dict[tuple[str, str], tuple[str, str] | None] = _discover()

# --- "context" → "page_context" alias ---
# Operation name is "context" but file is "page_context.py" (can't rename
# because every artifact also has a separate context.py with different logic).
for _art in list({k[0] for k in INFRA_OPS if k[1] == "page_context"}):
    INFRA_OPS[(_art, "context")] = INFRA_OPS[(_art, "page_context")]

# --- Attempt chat_* aliases (cross-operation routing) ---
INFRA_OPS.update({
    ("attempt", "chat_get"): (f"{_I}.attempt.chat.get", "get_chat_impl"),
    ("attempt", "chat_message"): (f"{_I}.attempt.message", "attempt_message_internal_impl"),
    ("attempt", "chat_stop"): (f"{_I}.attempt.stop", "attempt_stop_internal_impl"),
    ("attempt", "chat_end"): (f"{_I}.attempt.chat_complete", "chat_complete_attempt_impl"),
    ("attempt", "chat_voice"): (f"{_I}.attempt.audio_start", "audio_start_attempt_impl"),
    ("attempt", "chat_mute"): (f"{_I}.attempt.audio_mute", "audio_mute_attempt_impl"),
    ("attempt", "chat_silence"): (f"{_I}.attempt.audio_stop", "audio_stop_attempt_impl"),
    ("attempt", "chat_response"): (f"{_I}.attempt.response", "attempt_response_internal_impl"),
    # chat_grade, chat_feedback, chat_strengths, chat_improvements, chat_analyses, chat_hints
    # are auto-discovered from app/infra/attempt/chat_*.py
})

# --- Test overrides (non-standard function names) ---
INFRA_OPS.update({
    ("test", "grade"): ("app.infra.test.grade", "create_grade_impl"),
    ("test", "feedback"): ("app.infra.test.feedback", "create_feedback_impl"),
    # Mirrors attempt.chat_create — one invocation per LLM tool call.
    ("test", "invocation_create"): (
        "app.infra.invocation.create", "create_invocation_impl",
    ),
})

# --- Dashboard aliases ---
# Permissions namespace read-only dashboards under ``system``/``test``/``attempt``
# with a synthetic ``<source_artifact>_get`` operation so one tool (View
# Dashboards) can route across them. Only the dashboards whose ``get.py``
# exposes a standard ``*_impl`` callable are aliased here — others
# (activity/dashboard/leaderboard use ``*_impl_cached`` with positional
# request objects; home/practice/record have no infra impl at all) need
# canonical wrappers before they can be routed from tools. See the
# matching permission seeds in ``database/seeds/resources/permissions.py``.
for _alias, _source in [
    (("system",  "activity_get"),    ("activity",    "get")),
    (("attempt", "dashboard_get"),   ("dashboard",   "get")),
    (("system",  "health_get"),      ("health",      "get")),
    (("attempt", "home_get"),        ("home",        "get")),
    (("attempt", "leaderboard_get"), ("leaderboard", "get")),
    (("attempt", "practice_get"),    ("practice",    "get")),
    (("system",  "pricing_get"),     ("pricing",     "get")),
    (("attempt", "record_get"),      ("record",      "get")),
    (("test",    "benchmark_get"),   ("benchmark",   "get")),
    (("attempt", "reports_get"),     ("reports",     "get")),
]:
    if _source in INFRA_OPS:
        INFRA_OPS[_alias] = INFRA_OPS[_source]


# ---------------------------------------------------------------------------
# INFRA_ITEM_TYPES — auto-discovered from Pydantic item classes
#
# Convention: Create{Name}Item / Update{Name}Item in app.infra.{name}.types
# Used by execute_infra_operation to determine structured vs kwargs dispatch.
# ---------------------------------------------------------------------------

from app.registry.discover import discover_infra_item_types as _discover_items

INFRA_ITEM_TYPES: dict[tuple[str, str], tuple[str, str]] = _discover_items()

# --- Manual override: attempt chat_create uses ApiRequest directly ---
INFRA_ITEM_TYPES[("attempt", "chat_create")] = (
    f"{_I}.attempt.chat_create", "CreateAttemptChatApiRequest"
)

# --- Manual override: test invocation_create uses ApiRequest directly ---
INFRA_ITEM_TYPES[("test", "invocation_create")] = (
    f"{_I}.invocation.create", "CreateInvocationApiRequest"
)


# ---------------------------------------------------------------------------
# Lookup helpers (used by execute_infra_operation.py)
# ---------------------------------------------------------------------------


def resolve_item_class(
    artifact: str,
    operation: str,
) -> type | None:
    """Look up (artifact, operation) and return the imported Pydantic item class.

    Returns None if no item type is registered for this pair.
    """
    entry = INFRA_ITEM_TYPES.get((artifact, operation))
    if entry is None:
        return None
    module_path, class_name = entry
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def resolve_request_class(
    artifact: str,
    operation: str,
) -> type | None:
    """Derive the API request wrapper class from the item type entry.

    Convention: CreateFooItem → CreateFooApiRequest (same module).
    Returns None if no item type is registered.
    """
    entry = INFRA_ITEM_TYPES.get((artifact, operation))
    if entry is None:
        return None
    module_path, class_name = entry
    # CreateFooItem → CreateFooApiRequest, UpdateFooItem → UpdateFooApiRequest
    # PatchFooDraftApiRequest → already IS the request class (no wrapper)
    if class_name.endswith("ApiRequest"):
        # Draft-style: the item IS the request (flat, no wrapper)
        return None
    request_class_name = class_name.replace("Item", "ApiRequest")
    mod = importlib.import_module(module_path)
    return getattr(mod, request_class_name, None)


def get_accepted_fields(artifact: str, operation: str) -> set[str] | None:
    """Return the set of field names the item class accepts.

    Useful for validating that a tool's args_outputs only produce
    fields that the target operation understands.
    """
    cls = resolve_item_class(artifact, operation)
    if cls is None:
        return None
    return set(cls.model_fields.keys())
