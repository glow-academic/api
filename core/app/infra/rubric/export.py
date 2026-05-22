"""Rubric export — PDF generation with optional grading overlay.

`export_rubric_impl` composes tool-layer black boxes directly — it does
NOT route through `get_rubric_impl`. Reason: the editor composer
auto-creates a group for the caller's session (drafts, pending ops),
which a read-only PDF export doesn't need and fails when called
without a session_id.

The `rubric_id` on an attempt chat is a `rubrics_resource.id` (a
denormalised snapshot), not a `rubric_artifact.id`. The resource row
already carries the name, total_points, pass_points, and the list of
`standard_group_ids`, so we read from the resource layer and then fan
out to the standard_group + standard tool tools. No artifact/junction
hydration needed for PDF export.

Flow:
  1. resolve_profile_identity_context    → 401 if profile missing.
  2. get_rubrics (resource layer)        → 404 if not found; carries
                                            name + standard_group_ids.
  3. get_standard_groups + search_standards → structural bundle.
  4. Optional grading overlay when chat_id is provided:
       - search_attempt_grades             → latest grade_id for chat.
       - search_attempt_feedback_entries   → per-standard feedback.
       → derive achieved / passed / feedback maps.
  5. _render_rubric_pdf  — ReportLab (ported from v1 layout).
"""

from __future__ import annotations

import io
import os
import uuid as uuid_mod
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.types import ExportRubricApiResponse
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.infra.refresh.queue import enqueue_refreshes
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.entries.attempt_feedback.search import search_attempt_feedback_entries
from app.tools.entries.attempt_feedback.types import GetAttemptFeedbackResponse
from app.tools.entries.attempt_grade.search import search_attempt_grades
from app.tools.resources.rubrics.get import get_rubrics as get_rubrics_resource
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standard_groups.types import GetStandardGroupResponse
from app.tools.resources.standards.search import search_standards
from app.tools.resources.standards.types import GetStandardResponse


class _GradingState:
    """Derived grading overlay for a single grade_id.

    Mirrors v1's GradingState but keyed by str(UUID) for ReportLab
    lookups. Populated only when grade_id is supplied.
    """

    __slots__ = ("achieved_standards", "passed_standards", "feedback_by_standard_id")

    def __init__(
        self,
        achieved_standards: dict[str, bool],
        passed_standards: dict[str, bool],
        feedback_by_standard_id: dict[str, str],
    ) -> None:
        self.achieved_standards = achieved_standards
        self.passed_standards = passed_standards
        self.feedback_by_standard_id = feedback_by_standard_id


async def _load_grading_state(
    pool: asyncpg.Pool,
    grade_id: UUID,
    standards: list[GetStandardResponse],
    standard_groups: list[GetStandardGroupResponse],
) -> _GradingState:
    """Hydrate grading overlay via feedback entries (black-box impls)."""
    async with pool.acquire() as conn:
        feedbacks: list[GetAttemptFeedbackResponse] = (
            await search_attempt_feedback_entries(
                conn, redis, grade_ids=[grade_id], limit=1000
            )
        )

    # Map standard_id → latest feedback row (search returns DESC by
    # created_at; first occurrence wins).
    fb_by_sid: dict[UUID, GetAttemptFeedbackResponse] = {}
    for fb in feedbacks:
        if fb.standard_id and fb.standard_id not in fb_by_sid:
            fb_by_sid[fb.standard_id] = fb

    # Achieved: a feedback row exists for the standard.
    achieved_standards: dict[str, bool] = {
        str(sid): True for sid in fb_by_sid.keys()
    }

    # Passed per-group: sum feedback totals within each group, compare
    # to group.pass_points. Mark every standard in a group as passed
    # when the group total crosses its threshold. Mirrors v1 semantics.
    group_of_standard: dict[UUID, UUID] = {}
    for s in standards:
        if s.id is None or s.standard_group_id is None:
            continue
        group_of_standard[s.id] = s.standard_group_id

    pass_points_of_group: dict[UUID, int] = {}
    for sg in standard_groups:
        if sg.id is not None and sg.pass_points is not None:
            pass_points_of_group[sg.id] = sg.pass_points

    group_totals: dict[UUID, int] = {}
    for sid, fb in fb_by_sid.items():
        grp = group_of_standard.get(sid)
        if grp is not None:
            group_totals[grp] = group_totals.get(grp, 0) + (fb.total or 0)

    passed_standards: dict[str, bool] = {}
    for sid in fb_by_sid.keys():
        grp = group_of_standard.get(sid)
        threshold = pass_points_of_group.get(grp) if grp is not None else None
        total = group_totals.get(grp, 0) if grp is not None else 0
        passed_standards[str(sid)] = (
            threshold is not None and total >= threshold
        )

    feedback_by_standard_id: dict[str, str] = {
        str(sid): (fb.feedback or "") for sid, fb in fb_by_sid.items() if fb.feedback
    }

    return _GradingState(
        achieved_standards=achieved_standards,
        passed_standards=passed_standards,
        feedback_by_standard_id=feedback_by_standard_id,
    )


def _render_rubric_pdf(
    standard_groups: list[GetStandardGroupResponse],
    standards: list[GetStandardResponse],
    grading: _GradingState | None,
    title: str,
) -> bytes:
    """Render rubric as a PDF (layout ported from v1).

    Cells are coloured per-standard when grading is provided:
      achieved + passed → green (#bbf7d0)
      achieved + not passed → red (#fecaca)
    Feedback text is appended italic below a cell when available.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    # Build the grouped standards list sorted by points desc (matches
    # TableRubric's client-side ordering — highest-scoring standard
    # becomes the leftmost column within each group's row).
    standards_by_group: dict[UUID, list] = {}
    for s in standards:
        if s.standard_group_id is None or s.id is None:
            continue
        standards_by_group.setdefault(s.standard_group_id, []).append(s)

    grouped: list[tuple] = []
    for sg in standard_groups:
        if sg.id is None:
            continue
        stds = standards_by_group.get(sg.id, [])
        stds_sorted = sorted(stds, key=lambda x: (x.points or 0), reverse=True)
        grouped.append((sg, stds_sorted))

    max_standards = max((len(stds) for _, stds in grouped), default=0)
    if max_standards == 0:
        raise HTTPException(
            status_code=400, detail="No standards found in rubric"
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=title,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "CellStyle", parent=styles["Normal"], fontSize=7, leading=9,
        spaceBefore=0, spaceAfter=0,
    )
    cell_style_bold = ParagraphStyle(
        "CellStyleBold", parent=cell_style, fontName="Helvetica-Bold",
    )
    header_cell_style = ParagraphStyle(
        "HeaderCellStyle", parent=cell_style_bold, textColor=colors.white,
    )
    feedback_style = ParagraphStyle(
        "FeedbackStyle", parent=cell_style,
        fontName="Helvetica-Oblique", fontSize=6, leading=8,
        textColor=colors.HexColor("#333333"),
    )

    # Header row: "Criteria" + standard level labels taken from the
    # first group (v1 pattern; assumes parallel standard ordering).
    first_group_stds = grouped[0][1] if grouped else []
    header_row: list = [Paragraph("<b>Criteria</b>", header_cell_style)]
    for i in range(max_standards):
        label = ""
        if i < len(first_group_stds):
            std = first_group_stds[i]
            label = f"{std.name or ''} ({int(std.points or 0)})"
        header_row.append(Paragraph(f"<b>{label}</b>", header_cell_style))

    table_data: list[list] = [header_row]
    cell_bg: dict[tuple[int, int], object] = {}

    for row_idx, (group, stds) in enumerate(grouped):
        data_row_idx = row_idx + 1  # +1 for header
        row: list = [Paragraph(group.name or "Unknown", cell_style_bold)]
        for col_idx in range(max_standards):
            if col_idx >= len(stds):
                row.append(Paragraph("", cell_style))
                continue

            std = stds[col_idx]
            sid_key = str(std.id) if std.id else ""
            description_text = std.description or ""

            is_achieved = bool(
                grading and grading.achieved_standards.get(sid_key, False)
            )
            is_passed = bool(
                grading and grading.passed_standards.get(sid_key, False)
            )

            parts = [Paragraph(description_text, cell_style)]
            if is_achieved and grading:
                fb = grading.feedback_by_standard_id.get(sid_key)
                if fb:
                    parts.append(
                        Paragraph(f"<i>Feedback: {fb}</i>", feedback_style)
                    )

            row.append(parts[0] if len(parts) == 1 else parts)

            if is_achieved:
                cell_bg[(data_row_idx, col_idx + 1)] = (
                    colors.HexColor("#bbf7d0")
                    if is_passed
                    else colors.HexColor("#fecaca")
                )

        table_data.append(row)

    # Column widths: 20% criteria column, remaining evenly split.
    available_width = letter[0] - 1.0 * inch
    criteria_width = available_width * 0.20
    level_width = (available_width - criteria_width) / max_standards
    col_widths = [criteria_width] + [level_width] * max_standards

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_commands: list = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f9fafb"))
            )
    for (r, c), bg in cell_bg.items():
        style_commands.append(("BACKGROUND", (c, r), (c, r), bg))

    table.setStyle(TableStyle(style_commands))
    doc.build([table])

    buffer.seek(0)
    return buffer.getvalue()


async def export_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    rubric_id: UUID,
    session_id: UUID | None = None,
    chat_id: UUID | None = None,
) -> ExportRubricApiResponse:
    """Export a single rubric as a PDF (optionally filled with grades).

    File modality (same chain as every other artifact's export):
      build PDF bytes → write to disk → ``create_upload`` (mime_type
      ``application/pdf``) → ``create_file_resource`` →
      ``create_file_entry`` → ``create_file_upload`` →
      ``refresh_files_internal`` → return ``file_id``. The client then
      downloads via ``/rubric/file/download`` (BFF wrap at
      ``/api/rubric/download/{file_id}``).

    Args:
        pool: database pool
        redis: redis client (threaded through resource hydrators for
               per-request caching — no side effects here)
        profile_id: authenticated caller (existence check only)
        rubric_id: rubric to export
        chat_id: when provided, resolve the chat's latest grade and
                 overlay achieved/passed highlights + feedback on the
                 rendered cells. Without it, an empty rubric template
                 is returned. The chat concept scales to carry more
                 downstream context (analyses, notes, etc.) in future.
    """
    # 1. Auth — just verify the profile exists. No group/session work.
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again."
        )

    # 2. Resolve the rubric from `rubrics_resource` (the denormalised
    #    resource). The chat's `rubric_id` is a resource id (FK from
    #    attempt_chat_rubrics_connection), NOT a `rubric_artifact.id`,
    #    so we stay at the resource layer here. The resource row
    #    already carries name + standard_group_ids — no junction fan-
    #    out needed.
    async with pool.acquire() as conn:
        rubrics = await get_rubrics_resource(conn, [rubric_id], redis)
    if not rubrics:
        raise HTTPException(status_code=404, detail="Rubric not found")
    resource = rubrics[0]
    name = resource.name or "rubric"

    # 3. Hydrate standard_groups by id and standards by group filter.
    #    Standards are looked up via the group ids (search_standards
    #    accepts a standard_group_ids filter) — more direct than
    #    chasing another junction table.
    async with pool.acquire() as conn:
        standard_groups = await get_standard_groups(
            conn, list(resource.standard_group_ids or []), redis
        )
        standards = await search_standards(
            conn,
            redis,
            standard_group_ids=list(resource.standard_group_ids or []),
            limit_count=1000,
        )

    # 4. Optional grading overlay — resolve chat_id → latest grade.
    grading: _GradingState | None = None
    if chat_id is not None:
        # search_attempt_grades returns newest first (ORDER BY
        # created_at DESC); pick the head so retried gradings surface
        # the most recent attempt.
        async with pool.acquire() as conn:
            grades = await search_attempt_grades(
                conn, redis, chat_ids=[chat_id], limit=1
            )
        if not grades:
            raise HTTPException(
                status_code=404, detail="No grade found for chat"
            )
        grade_id = grades[0].grade_id
        grading = await _load_grading_state(
            pool, grade_id, standards, standard_groups
        )

    # 5. Render. `name` was resolved from the resource row above.
    pdf_bytes = _render_rubric_pdf(
        standard_groups, standards, grading, title=name
    )

    # 6. File-modality upload chain (mirrors persona/export.py).
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"{name}_{timestamp}.pdf"
    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.pdf"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(pdf_bytes)

    async with pool.acquire() as conn:
        upload_row = await create_upload(
            conn,
            redis, session_id=session_id,
            file_path=relative_path,
            mime_type="application/pdf",
            size=len(pdf_bytes),
        )
        resource_row = await create_file_resource(conn, redis)
        if session_id is not None:
            entry_row = await create_file_entry(
                conn,
                redis,
                session_id=session_id,
                files_id=resource_row.id,
            )
            await create_file_upload(
                conn,
                redis, file_id=entry_row.id,
                upload_id=upload_row.id,
                session_id=session_id,
            )

    await enqueue_refreshes(
        pool, redis, profile_id=profile_id, session_id=session_id,
        artifact_type="file", targets=["files_mv"], tags=["files"],
    )

    # row_count = number of rubric standards rendered (closest analogue
    # to CSV row count for schema symmetry across artifacts).
    return ExportRubricApiResponse(
        file_id=resource_row.id,
        file_name=file_name,
        row_count=len(standards),
    )
