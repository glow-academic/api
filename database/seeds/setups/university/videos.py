"""University video seed definitions.

Maps scenarios to source video files.
The runner copies each source file, creates the full video entry chain
via create_scenario_video. The scenario already references the
deterministic videos_resource_id set at scenario creation time.

Source files live in uploads/video/ at the project root.
"""

from database.seeds.setups.university.scenarios import (
    ACADEMIC_INTEGRITY_SCENARIO,
    ACADEMIC_INTEGRITY_VIDEO,
    FERPA_SCENARIO,
    FERPA_VIDEO,
    UPSET_STUDENT_SCENARIO,
    UPSET_STUDENT_VIDEO,
)

# ---------------------------------------------------------------------------
# Scenario → source video file mapping
# ---------------------------------------------------------------------------

scenario_videos = [
    dict(
        scenario_id=ACADEMIC_INTEGRITY_SCENARIO,
        videos_resource_id=ACADEMIC_INTEGRITY_VIDEO,
        source_file="video/cheating.mp4",
        mime_type="video/mp4",
        name="Academic Integrity",
        description="Video demonstrating an academic integrity violation scenario",
        length_seconds=8,
    ),
    dict(
        scenario_id=FERPA_SCENARIO,
        videos_resource_id=FERPA_VIDEO,
        source_file="video/ferpa.mp4",
        mime_type="video/mp4",
        name="FERPA Compliance",
        description="Video demonstrating a FERPA privacy violation scenario",
        length_seconds=8,
    ),
    dict(
        scenario_id=UPSET_STUDENT_SCENARIO,
        videos_resource_id=UPSET_STUDENT_VIDEO,
        source_file="video/upset.mp4",
        mime_type="video/mp4",
        name="Upset Student",
        description="Video demonstrating an upset student scenario requiring de-escalation",
        length_seconds=8,
    ),
]
