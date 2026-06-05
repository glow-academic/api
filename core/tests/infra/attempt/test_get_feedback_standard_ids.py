"""Regression: /attempt/get feedback loop must read plural ``standard_ids``.

Background (live 500): the chat-feedback loop in
``app.infra.attempt.get.get_attempt_internal`` referenced
``feedback.standard_id`` (SINGULAR) while the feedback schema
``GetAttemptFeedbackResponse`` exposes ``standard_ids: list[UUID]`` (PLURAL).
Every graded attempt with chat feedback therefore raised
``AttributeError: 'GetAttemptFeedbackResponse' object has no attribute
'standard_id'`` -> HTTP 500 -> the attempt-review page hit its error boundary.

These tests are modular (deps as params): they exercise the exact transform
the handler performs over feedback objects, using the REAL schema
(``GetAttemptFeedbackResponse``), the REAL output model (``FeedbackEntry``) and
the REAL helper functions (``compute_achieved_standards`` /
``compute_passed_standards``) -- no DB / redis. fail-pre proves the singular
access raised AttributeError; pass-post proves the plural handling is correct.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infra.attempt.permissions import (
    compute_achieved_standards,
    compute_passed_standards,
)
from app.infra.attempt.types import FeedbackEntry
from app.tools.entries.attempt_feedback.types import GetAttemptFeedbackResponse


def _make_feedback(standard_ids, total=8, feedback="good work"):
    return GetAttemptFeedbackResponse(
        feedback_id=uuid4(),
        grade_id=uuid4(),
        standard_ids=list(standard_ids),
        total=total,
        feedback=feedback,
        created_at=datetime.now(timezone.utc),
    )


def _build_feedback_entries(chat_feedbacks, standards_meta):
    """Mirror of the handler's per-standard FeedbackEntry build (get.py)."""
    feedbacks: list[FeedbackEntry] = []
    for feedback in chat_feedbacks:
        std_ids = feedback.standard_ids or [None]
        for std_id in std_ids:
            std_group_id = None
            if std_id:
                std_meta = standards_meta.get(std_id, {})
                std_group_id = std_meta.get("standard_group_id")
            feedbacks.append(
                FeedbackEntry(
                    id=feedback.feedback_id,
                    standard_id=std_id,
                    standard_group_id=std_group_id,
                    total=feedback.total,
                    feedback=feedback.feedback,
                )
            )
    return feedbacks


def test_schema_has_plural_standard_ids_not_singular():
    """Guard: the schema is plural. The old code read the missing singular."""
    fields = GetAttemptFeedbackResponse.model_fields
    assert "standard_ids" in fields
    assert "standard_id" not in fields


def test_singular_access_raises_attributeerror_fail_pre():
    """fail-pre: the original ``feedback.standard_id`` access blows up.

    This is exactly what produced the live 500.
    """
    fb = _make_feedback([uuid4()])
    with pytest.raises(AttributeError):
        _ = fb.standard_id  # noqa: B018 -- intentional: reproduce the bug


def test_feedback_entries_one_per_standard_id():
    """pass-post: a multi-standard feedback expands to one entry per standard,
    each resolving its own standard_group_id from standards metadata."""
    sg_a, sg_b = uuid4(), uuid4()
    std_a, std_b = uuid4(), uuid4()
    standards_meta = {
        std_a: {"standard_group_id": sg_a},
        std_b: {"standard_group_id": sg_b},
    }
    fb = _make_feedback([std_a, std_b], total=7, feedback="solid")

    entries = _build_feedback_entries([fb], standards_meta)

    assert len(entries) == 2
    by_std = {e.standard_id: e for e in entries}
    assert by_std[std_a].standard_group_id == sg_a
    assert by_std[std_b].standard_group_id == sg_b
    # shared feedback fields propagate to every per-standard entry
    for e in entries:
        assert e.id == fb.feedback_id
        assert e.total == 7
        assert e.feedback == "solid"


def test_feedback_entries_empty_standard_ids_surfaces_once():
    """pass-post: a feedback with no standards still surfaces once (standard_id
    None) so review-page feedback text is not silently dropped."""
    fb = _make_feedback([], total=3, feedback="general note")
    entries = _build_feedback_entries([fb], {})
    assert len(entries) == 1
    assert entries[0].standard_id is None
    assert entries[0].standard_group_id is None
    assert entries[0].feedback == "general note"


def test_grading_state_helpers_consume_flattened_dicts():
    """pass-post: the achieved/passed helpers (singular ``standard_id`` keys)
    work once the plural list is flattened, mirroring the handler."""
    sg = uuid4()
    std_a, std_b = uuid4(), uuid4()
    standards_meta = {
        std_a: {"standard_group_id": sg},
        std_b: {"standard_group_id": sg},
    }
    standard_groups_meta = {sg: {"pass_points": 5.0}}
    fb = _make_feedback([std_a, std_b], total=6)

    feedbacks_dicts = [
        {"standard_id": std_id, "total": fb.total}
        for std_id in fb.standard_ids
    ]
    assert len(feedbacks_dicts) == 2

    achieved = compute_achieved_standards(feedbacks_dicts)
    assert {a["standard_id"] for a in achieved} == {std_a, std_b}
    assert all(a["achieved"] for a in achieved)

    passed = compute_passed_standards(
        feedbacks_dicts, standard_groups_meta, standards_meta
    )
    # total 6 >= pass_points 5 -> all passed
    assert {p["standard_id"] for p in passed} == {std_a, std_b}
    assert all(p["passed"] for p in passed)


def test_handler_source_no_longer_reads_singular_standard_id():
    """Belt-and-suspenders: the handler source must not reference the missing
    singular attribute on feedback objects again (schema-drift guard)."""
    import re

    import app.infra.attempt.get as mod

    source = open(mod.__file__).read()
    # word boundary so ``feedback.standard_ids`` (plural) does not match
    assert not re.search(r"feedback\.standard_id\b", source)
    assert "feedback.standard_ids" in source
