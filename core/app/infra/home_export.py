"""Home export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_attempts — full dump (all entries, no filters, no pagination)
  3. Resource get tools — parallel hydration (profiles, simulations, scenarios, etc.)
  4. Certificate score computation from attempt data
  5. PDF certificate generation via ReportLab
  6. ZIP generation (attempts.csv + certificate.pdf) + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import os
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.home.types import ExportHomeApiResponse
from app.tools.entries.attempt.search import search_attempts
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.personas.get import get_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.simulations.get import get_simulations
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

PIPE = "|"

ATTEMPT_CSV_COLUMNS = [
    "attempt_id",
    "attempt_date",
    "profile",
    "simulation",
    "scenarios",
    "persona",
    "cohort",
    "department",
    "practice",
    "infinite_mode",
    "num_chats",
    "archived",
]


@dataclass
class SimulationResult:
    """Simulation result for certificate rendering."""

    name: str
    score: int
    passed: bool


@dataclass
class CohortResult:
    """Cohort result for certificate rendering."""

    name: str
    passed: bool
    simulations: list[SimulationResult] = field(default_factory=list)


def _generate_certificate_pdf(
    profile_name: str,
    cohorts: list[CohortResult],
) -> bytes:
    """Generate a certificate PDF using ReportLab. Falls back to plain text."""
    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.lib.styles import (
            ParagraphStyle,  # type: ignore
            getSampleStyleSheet,  # type: ignore
        )
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.platypus import (
            Frame,  # type: ignore
            PageTemplate,  # type: ignore
            Paragraph,  # type: ignore
            SimpleDocTemplate,  # type: ignore
            Spacer,  # type: ignore
            Table,  # type: ignore
            TableStyle,  # type: ignore
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )
        story = []

        content_frame = Frame(
            doc.leftMargin + 0.2 * inch,
            doc.bottomMargin + 0.2 * inch,
            doc.width - 0.4 * inch,
            doc.height - 0.4 * inch,
            leftPadding=0.1 * inch,
            bottomPadding=0.1 * inch,
            rightPadding=0.1 * inch,
            topPadding=0.1 * inch,
            showBoundary=1,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,
            textColor=colors.darkblue,
        )
        name_style = ParagraphStyle(
            "NameStyle",
            parent=styles["Heading2"],
            fontSize=28,
            spaceAfter=20,
            alignment=1,
            textColor=colors.black,
        )
        status_style = ParagraphStyle(
            "StatusStyle",
            parent=styles["Heading2"],
            fontSize=20,
            spaceAfter=30,
            alignment=1,
            fontWeight="bold",
        )
        header_style = ParagraphStyle(
            "HeaderStyle",
            parent=styles["Heading3"],
            fontSize=14,
            spaceAfter=10,
            textColor=colors.darkblue,
        )

        story.append(Paragraph("Certificate of Completion", title_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph(profile_name, name_style))
        story.append(Spacer(1, 30))

        total_cohorts = len(cohorts)
        passed_cohorts = sum(1 for cohort in cohorts if cohort.passed)
        all_passed = passed_cohorts == total_cohorts and total_cohorts > 0

        if all_passed:
            status_text = "COMPLETE"
            status_color = colors.green
        else:
            status_text = "INCOMPLETE"
            status_color = colors.red

        status_style.textColor = status_color
        story.append(Paragraph(status_text, status_style))
        story.append(Spacer(1, 30))

        summary_text = (
            f"Progress: {passed_cohorts} of {total_cohorts} cohorts completed"
        )
        story.append(Paragraph(summary_text, styles["Normal"]))
        story.append(Spacer(1, 20))

        if cohorts:
            story.append(Paragraph("Cohort Progress", header_style))

            def truncate_text(text: str, max_length: int = 24) -> str:
                if len(text) <= max_length:
                    return text
                return text[: max_length - 3] + "..."

            table_data = [["Cohort", "Simulation", "Score", "Status"]]

            for cohort in cohorts:
                cohort_name = cohort.name or "Unknown Cohort"
                truncated_cohort_name = truncate_text(cohort_name)

                for sim in cohort.simulations or []:
                    sim_name = sim.name or "Unknown Simulation"
                    score = sim.score or 0
                    passed = sim.passed or False

                    score_int = int(round(float(score))) if score > 0 else 0
                    score_text = f"{score_int}%" if score_int > 0 else "No attempts"
                    row_status = (
                        "PASS"
                        if passed
                        else "FAIL"
                        if score_int > 0
                        else "Not attempted"
                    )

                    table_data.append(
                        [truncated_cohort_name, sim_name, score_text, row_status]
                    )

            table = Table(
                table_data, colWidths=[1.8 * inch, 2.5 * inch, 1 * inch, 1 * inch]
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
                        ("GRID", (0, 0), (-1, -1), 1, colors.darkblue),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 9),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("WORDWRAP", (0, 0), (-1, -1), True),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                    ]
                )
            )

            story.append(table)
            story.append(Spacer(1, 30))

        def certificate_page(canvas: Any, doc: Any) -> None:  # type: ignore  # noqa: ANN401
            canvas.setStrokeColor(colors.darkblue)
            canvas.setLineWidth(3)
            canvas.rect(
                doc.leftMargin + 0.1 * inch,
                doc.bottomMargin + 0.1 * inch,
                doc.width - 0.2 * inch,
                doc.height - 0.2 * inch,
            )
            canvas.setLineWidth(1)
            canvas.rect(
                doc.leftMargin + 0.2 * inch,
                doc.bottomMargin + 0.2 * inch,
                doc.width - 0.4 * inch,
                doc.height - 0.4 * inch,
            )
            canvas.setFillColor(colors.lightblue)
            corner_size = 0.15 * inch
            for x, y in [
                (
                    doc.leftMargin + 0.1 * inch,
                    doc.bottomMargin + doc.height - 0.25 * inch,
                ),
                (
                    doc.leftMargin + doc.width - 0.25 * inch,
                    doc.bottomMargin + doc.height - 0.25 * inch,
                ),
                (doc.leftMargin + 0.1 * inch, doc.bottomMargin + 0.1 * inch),
                (
                    doc.leftMargin + doc.width - 0.25 * inch,
                    doc.bottomMargin + 0.1 * inch,
                ),
            ]:
                canvas.rect(x, y, corner_size, corner_size, fill=1)

            canvas.setFont("Helvetica", 10)
            canvas.setFillColor(colors.darkblue)
            canvas.drawString(
                doc.leftMargin + 0.3 * inch,
                doc.bottomMargin + 0.3 * inch,
                "GLOW | Purdue University",
            )

        page_template = PageTemplate(
            id="certificate", frames=[content_frame], onPage=certificate_page
        )
        doc.addPageTemplates([page_template])
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    except ImportError:
        logger.warning("ReportLab not available, using simple text generation")
        return _generate_certificate_text(profile_name, cohorts)


def _generate_certificate_text(
    profile_name: str,
    cohorts: list[CohortResult],
) -> bytes:
    """Fallback plain text certificate."""
    text_content = []
    text_content.append("Certificate of Completion")
    text_content.append("=" * 30)
    text_content.append("")
    text_content.append(f"Name: {profile_name}")
    text_content.append("")

    total_cohorts = len(cohorts)
    passed_cohorts = sum(1 for cohort in cohorts if cohort.passed)
    all_passed = passed_cohorts == total_cohorts and total_cohorts > 0

    text_content.append(f"Status: {'COMPLETE' if all_passed else 'INCOMPLETE'}")
    text_content.append(
        f"Progress: {passed_cohorts} of {total_cohorts} cohorts completed"
    )
    text_content.append("")
    text_content.append("Cohort Progress:")
    text_content.append("-" * 20)

    for cohort in cohorts:
        cohort_name = cohort.name or "Unknown Cohort"
        text_content.append(f"\n{cohort_name}:")
        for sim in cohort.simulations or []:
            sim_name = sim.name or "Unknown Simulation"
            score = sim.score or 0
            passed = sim.passed or False
            score_int = int(round(float(score))) if score > 0 else 0
            score_text = f"{score_int}%" if score_int > 0 else "No attempts"
            status_text = (
                "PASS" if passed else "FAIL" if score_int > 0 else "Not attempted"
            )
            text_content.append(f"  - {sim_name}: {score_text} ({status_text})")

    text_content.append("")
    text_content.append("GLOW | Purdue University")

    return "\n".join(text_content).encode("utf-8")


def _try_pdfa_conversion(pdf_bytes: bytes) -> bytes:
    """Best-effort PDF/A-2b conversion via Ghostscript."""
    try:

        def find_srgb_icc() -> str | None:
            candidate_paths = [
                "/usr/share/color/icc/ghostscript/srgb.icc",
                "/usr/share/color/icc/srgb.icc",
                "/usr/share/icc/colord/sRGB.icc",
                "/usr/share/ghostscript/iccprofiles/srgb.icc",
                "/usr/share/ghostscript/10.00.0/iccprofiles/srgb.icc",
                "/usr/share/ghostscript/9.56.1/iccprofiles/srgb.icc",
            ]
            for path in candidate_paths:
                if os.path.exists(path):
                    return path
            return None

        srgb_icc = find_srgb_icc()

        with (
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as in_file,
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as out_file,
        ):
            in_file.write(pdf_bytes)
            in_file.flush()

            gs_cmd = [
                "gs",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pdfwrite",
                "-dPDFSETTINGS=/prepress",
                "-sProcessColorModel=DeviceRGB",
                "-sColorConversionStrategy=sRGB",
                "-dUseCIEColor",
                "-dPDFA=2",
                "-dPDFACompatibilityPolicy=1",
                f"-sOutputFile={out_file.name}",
            ]

            if srgb_icc:
                gs_cmd.append(f"-sOutputICCProfile={srgb_icc}")

            gs_cmd.append(in_file.name)

            proc = subprocess.run(gs_cmd, capture_output=True, text=True)
            if (
                proc.returncode == 0
                and os.path.exists(out_file.name)
                and os.path.getsize(out_file.name) > 0
            ):
                with open(out_file.name, "rb") as f_out:
                    return f_out.read()
            else:
                logger.warning(
                    "Ghostscript PDF/A conversion failed; returning original PDF. stderr=%s",
                    proc.stderr,
                )
    except FileNotFoundError:
        logger.info("Ghostscript not found; returning non-PDF/A PDF")
    except Exception as conv_err:
        logger.warning(
            "PDF/A conversion error; returning original PDF: %s", str(conv_err)
        )

    return pdf_bytes


def _compute_cert_from_attempts(
    attempts: list[Any],
    profile_map: dict[UUID, str],
    simulation_map: dict[UUID, str],
    cohort_map: dict[UUID, str],
    simulations_data: list[Any],
    cohorts_data: list[Any],
    profile_id: UUID,
) -> tuple[str, list[CohortResult]]:
    """Compute certificate scores from attempt data + hydrated resources."""
    profile_name = profile_map.get(profile_id, "Unknown")

    # Filter active cohorts/simulations
    active_cohort_ids = {c.id for c in cohorts_data if c.active}
    active_simulation_ids = {s.id for s in simulations_data if s.active}

    # Filter to general (non-practice) attempts with active cohort/simulation
    relevant = [
        a
        for a in attempts
        if not a.practice
        and not a.is_archived
        and a.cohort_id in active_cohort_ids
        and a.simulation_id in active_simulation_ids
    ]

    if not relevant:
        return profile_name, []

    # Group by (simulation_id) — take best attempt per simulation
    sim_scores: dict[UUID, list[int]] = defaultdict(list)

    for a in relevant:
        if a.simulation_id:
            # num_chats as a proxy for completion — if they have chats, count it
            sim_scores[a.simulation_id].append(a.num_chats)

    # Build cohort -> simulation structure
    cohort_sim_ids: dict[UUID, set[UUID]] = defaultdict(set)
    for a in relevant:
        if a.cohort_id and a.simulation_id:
            cohort_sim_ids[a.cohort_id].add(a.simulation_id)

    cohort_results: list[CohortResult] = []
    for cohort_id in sorted(
        cohort_sim_ids.keys(), key=lambda cid: cohort_map.get(cid, "")
    ):
        sims = []
        for sim_id in cohort_sim_ids[cohort_id]:
            # We don't have grade data from search_attempts, so mark as attempted
            has_attempts = len(sim_scores.get(sim_id, [])) > 0
            sims.append(
                SimulationResult(
                    name=simulation_map.get(sim_id, "Unknown Simulation"),
                    score=0,  # Grade data not available from attempt MV
                    passed=has_attempts,
                )
            )
        cohort_passed = all(s.passed for s in sims) if sims else False
        cohort_results.append(
            CohortResult(
                name=cohort_map.get(cohort_id, "Unknown Cohort"),
                passed=cohort_passed,
                simulations=sims,
            )
        )

    return profile_name, cohort_results


async def export_home_client(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
) -> ExportHomeApiResponse:
    """Home full export using composable infra functions."""
    from fastapi import HTTPException

    # -- Step 1: Profile context --
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again."
        )

    # -- Step 2: Search all attempts (full dump) --
    async with pool.acquire() as conn:
        attempts, _total_count = await search_attempts(conn, limit=100000, offset=0)

    if not attempts:
        return ExportHomeApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Parallel resource hydration --
    all_profile_ids: set[UUID] = set()
    all_simulation_ids: set[UUID] = set()
    all_scenario_ids: set[UUID] = set()
    all_persona_ids: set[UUID] = set()
    all_cohort_ids: set[UUID] = set()
    all_department_ids: set[UUID] = set()

    for a in attempts:
        if a.profile_id:
            all_profile_ids.add(a.profile_id)
        if a.simulation_id:
            all_simulation_ids.add(a.simulation_id)
        if a.scenario_ids:
            all_scenario_ids.update(a.scenario_ids)
        if a.personas_id:
            all_persona_ids.add(a.personas_id)
        if a.cohort_id:
            all_cohort_ids.add(a.cohort_id)
        if a.department_id:
            all_department_ids.add(a.department_id)

    async def _empty() -> list[Any]:
        return []

    async def _get_profiles() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_profiles(conn, list(all_profile_ids), redis)

    async def _get_simulations() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_simulations(conn, list(all_simulation_ids), redis)

    async def _get_scenarios() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_scenarios(conn, list(all_scenario_ids), redis)

    async def _get_personas() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_personas(conn, list(all_persona_ids), redis)

    async def _get_cohorts() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_cohorts(conn, list(all_cohort_ids), redis)

    async def _get_departments() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_departments(conn, list(all_department_ids), redis)

    (
        profiles_data,
        simulations_data,
        scenarios_data,
        personas_data,
        cohorts_data,
        departments_data,
    ) = await asyncio.gather(
        _get_profiles() if all_profile_ids else _empty(),
        _get_simulations() if all_simulation_ids else _empty(),
        _get_scenarios() if all_scenario_ids else _empty(),
        _get_personas() if all_persona_ids else _empty(),
        _get_cohorts() if all_cohort_ids else _empty(),
        _get_departments() if all_department_ids else _empty(),
    )

    profile_map = {p.id: p.name or "" for p in profiles_data}
    simulation_map = {s.id: s.name or "" for s in simulations_data}
    scenario_map = {s.id: s.name or "" for s in scenarios_data}
    persona_map = {p.id: p.name or "" for p in personas_data}
    cohort_map = {c.id: c.name or "" for c in cohorts_data}
    department_map = {d.id: d.name or "" for d in departments_data}

    # -- Step 4: Generate attempts CSV --
    attempts_output = io.StringIO()
    attempts_writer = csv.writer(attempts_output)
    attempts_writer.writerow(ATTEMPT_CSV_COLUMNS)

    for a in attempts:
        scenarios_str = PIPE.join(
            scenario_map.get(sid, "") for sid in (a.scenario_ids or [])
        )
        attempts_writer.writerow(
            [
                str(a.attempt_id),
                str(a.attempt_created_at),
                profile_map.get(a.profile_id, "") if a.profile_id else "",
                simulation_map.get(a.simulation_id, "") if a.simulation_id else "",
                scenarios_str,
                persona_map.get(a.personas_id, "") if a.personas_id else "",
                cohort_map.get(a.cohort_id, "") if a.cohort_id else "",
                department_map.get(a.department_id, "") if a.department_id else "",
                "Yes" if a.practice else "No",
                "Yes" if a.infinite_mode else "No",
                str(a.num_chats),
                "Yes" if a.is_archived else "No",
            ]
        )

    # -- Step 5: Compute certificate + generate PDF --
    profile_name, cohort_results = _compute_cert_from_attempts(
        attempts,
        profile_map,
        simulation_map,
        cohort_map,
        simulations_data,
        cohorts_data,
        profile_id,
    )

    # -- Step 6: Generate ZIP (attempts.csv + certificate.pdf) + upload --
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("attempts.csv", attempts_output.getvalue())
        if cohort_results:
            pdf_bytes = _generate_certificate_pdf(profile_name, cohort_results)
            is_pdf = pdf_bytes[:4] == b"%PDF"
            if is_pdf:
                pdf_bytes = _try_pdfa_conversion(pdf_bytes)
                zf.writestr("certificate.pdf", pdf_bytes)
            else:
                zf.writestr("certificate.txt", pdf_bytes)

    zip_content = zip_buffer.getvalue()
    row_count = len(attempts)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"home_export_{timestamp}.zip"

    return ExportHomeApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
