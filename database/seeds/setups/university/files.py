"""University file upload seed definitions.

Maps document IDs to source PDF files.
The runner reads each source file, creates the full file entry chain
via create_document_file, then links the result to the document via
document_files_junction.

Source files live in uploads/ at the project root.
"""

from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    ACADEMIC_INTEGRITY_FILES,
    FERPA_GENERAL,
    FERPA_GENERAL_FILES,
    FERPA_POLICY,
    FERPA_POLICY_FILES,
)

# ---------------------------------------------------------------------------
# Document → source file mapping
# ---------------------------------------------------------------------------

# Each entry maps a document to a file in the uploads/ asset dir.
# files_resource_id uses the same deterministic sid() from documents.py
# so documents_resource.file_id is already set at document creation time.
#
# The runner reads the file and runs the full chain:
#   copy file → create_upload → create_file_resource(id=files_resource_id)
#   → create_file_entry → create_file_upload

document_files = [
    dict(
        document_id=FERPA_POLICY,
        files_resource_id=FERPA_POLICY_FILES,
        source_file="FERPA.pdf",
        mime_type="application/pdf",
    ),
    dict(
        document_id=FERPA_GENERAL,
        files_resource_id=FERPA_GENERAL_FILES,
        source_file="FERPA.pdf",
        mime_type="application/pdf",
    ),
    dict(
        document_id=ACADEMIC_INTEGRITY_POLICY,
        files_resource_id=ACADEMIC_INTEGRITY_FILES,
        source_file="integrity.pdf",
        mime_type="application/pdf",
    ),
]
