"""University file upload seed definitions.

Maps document IDs to source PDF files.
The runner reads each source file, creates the full file entry chain
via create_document_file, then links the result to the document via
document_files_junction.

Source files live in database/output/setups/university/uploads/files/.
"""

from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    FERPA_GENERAL,
    FERPA_POLICY,
)

# ---------------------------------------------------------------------------
# Document → source file mapping
# ---------------------------------------------------------------------------

# Each entry maps a document to a file in the uploads/files/ asset dir.
# The runner reads the file and runs the full chain:
#   copy file → create_upload → create_file_resource
#   → create_file_entry → create_file_upload → junction INSERT

document_files = [
    dict(
        document_id=FERPA_POLICY,
        source_file="FERPA.pdf",
        mime_type="application/pdf",
    ),
    dict(
        document_id=FERPA_GENERAL,
        source_file="FERPA.pdf",
        mime_type="application/pdf",
    ),
    dict(
        document_id=ACADEMIC_INTEGRITY_POLICY,
        source_file="integrity.pdf",
        mime_type="application/pdf",
    ),
]
