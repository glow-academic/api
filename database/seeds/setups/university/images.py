"""University image seed definitions.

Maps documents to source image files for preview thumbnails.
Also creates standalone images (e.g. classroom) available for selection.

Source files live in uploads/image/ at the project root.
"""

from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    ACADEMIC_INTEGRITY_IMAGE,
    CLASSROOM_IMAGE,
    FERPA_POLICY,
    FERPA_POLICY_IMAGE,
)

# ---------------------------------------------------------------------------
# Standalone images — available for selection but not linked to documents
# ---------------------------------------------------------------------------

standalone_images = [
    dict(
        images_resource_id=CLASSROOM_IMAGE,
        source_file="image/classroom.jpg",
        mime_type="image/jpeg",
        name="Classroom",
        description="University classroom environment",
    ),
]

# ---------------------------------------------------------------------------
# Document → image mapping (first page preview for each document)
# ---------------------------------------------------------------------------

document_images = [
    dict(
        document_id=FERPA_POLICY,
        images_resource_id=FERPA_POLICY_IMAGE,
        source_file="image/ferpa-policy-page1.png",
        mime_type="image/png",
        name="FERPA Policy Preview",
        description="First page preview of the FERPA Policy document",
    ),
    dict(
        document_id=ACADEMIC_INTEGRITY_POLICY,
        images_resource_id=ACADEMIC_INTEGRITY_IMAGE,
        source_file="image/academic-integrity-policy-page1.png",
        mime_type="image/png",
        name="Academic Integrity Policy Preview",
        description="First page preview of the Academic Integrity Policy document",
    ),
]
