"""Rubric export — PDF generation with optional grading overlay.

Canonical infra impl: `export_rubric_impl` composes black-box tools to
produce a filled-or-empty rubric PDF.

Flow:
  1. get_rubric_impl            — hydrated rubric (names, descriptions,
                                   standard_groups, standards, points).
  2. (optional) grading hydration when grade_id is provided:
       - search_attempt_feedback_entries → per-standard feedback rows
       - get_attempt_grades              → grade-level score/passed
       → derive achieved_standards, passed_standards, feedback map.
  3. _render_rubric_pdf         — ReportLab (ported from v1 layout).

Returns: raw PDF bytes + suggested filename.
"""

from __future__ import annotations

import base64
import io
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.rubric.get import get_rubric_impl
from app.infra.rubric.types import ExportRubricApiResponse, GetRubricApiResponse
from app.tools.entries.attempt_feedback.search import search_attempt_feedback_entries
from app.tools.entries.attempt_feedback.types import GetAttemptFeedbackResponse
from app.tools.entries.attempt_grade.get import get_attempt_grades


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
    rubric: GetRubricApiResponse,
) -> _GradingState:
    """Hydrate grading overlay via feedback entries (black-box impls)."""
    async with pool.acquire() as conn:
        feedbacks: list[GetAttemptFeedbackResponse] = (
            await search_attempt_feedback_entries(
                conn, grade_ids=[grade_id], limit=1000
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
    # Build group_id → [standard_ids] and group_id → pass_points maps
    # from the rubric structure.
    group_of_standard: dict[UUID, UUID] = {}
    standards_in_group: dict[UUID, list[UUID]] = {}
    for s in rubric.standards or []:
        if s.id is None or s.standard_group_id is None:
            continue
        group_of_standard[s.id] = s.standard_group_id
        standards_in_group.setdefault(s.standard_group_id, []).append(s.id)

    pass_points_of_group: dict[UUID, int] = {}
    for sg in rubric.standard_groups or []:
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


def _selected_name(rubric: GetRubricApiResponse) -> str:
    """Pick the selected rubric name, falling back to 'rubric'."""
    for n in rubric.names or []:
        if n.selected and n.name:
            return n.name
    for n in rubric.names or []:
        if n.name:
            return n.name
    return "rubric"


def _render_rubric_pdf(
    rubric: GetRubricApiResponse,
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
    for s in rubric.standards or []:
        if s.standard_group_id is None or s.id is None:
            continue
        standards_by_group.setdefault(s.standard_group_id, []).append(s)

    grouped: list[tuple] = []
    for sg in rubric.standard_groups or []:
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
    grade_id: UUID | None = None,
) -> ExportRubricApiResponse:
    """Export a single rubric as a PDF (optionally filled with grades).

    Returns an `ExportRubricApiResponse` with base64-encoded PDF bytes
    in `content`. HTTP callers decode back to raw bytes before emitting
    a binary response; WS callers pass the response through the audit
    layer (which JSON-serializes it for the `.completed` event) so
    downstream subscribers receive the same envelope as the former CSV
    export.

    Args:
        pool: database pool
        redis: redis client (used by get_rubric_impl's cache)
        profile_id: authenticated caller
        rubric_id: rubric to export
        grade_id: when provided, highlight achieved/passed cells and
                  render feedback text; otherwise render an empty
                  template.
    """
    rubric = await get_rubric_impl(
        pool, redis, profile_id=profile_id, rubric_id=rubric_id
    )
    if rubric.rubric_exists is False:
        raise HTTPException(status_code=404, detail="Rubric not found")

    grading: _GradingState | None = None
    if grade_id is not None:
        # Validate grade_id exists before touching feedbacks.
        async with pool.acquire() as conn:
            grades = await get_attempt_grades(conn, [grade_id])
        if not grades:
            raise HTTPException(status_code=404, detail="Grade not found")
        grading = await _load_grading_state(pool, grade_id, rubric)

    name = _selected_name(rubric)
    pdf_bytes = _render_rubric_pdf(rubric, grading, title=name)

    # Row count loses its CSV meaning here; we keep the field for
    # schema stability and populate it with the standard count, which
    # is the closest analogue ("rows of the rubric table body").
    row_count = len(rubric.standards or [])

    return ExportRubricApiResponse(
        content=base64.b64encode(pdf_bytes).decode("ascii"),
        file_name=f"{name}.pdf",
        mime_type="application/pdf",
        row_count=row_count,
    )
