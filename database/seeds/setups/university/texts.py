"""University text upload seed definitions.

Maps document IDs to source text files (HTML content stored as .txt).
The runner reads each source file, creates the full text entry chain
via create_document_text, then links the result to the document via
update_document(text_ids=[...]).

Source files live in database/output/setups/university/uploads/files/text/.
"""

from database.seeds.setups.university.documents import (
    ACADEMIC_INTEGRITY_POLICY,
    HOMEWORK_TEMPLATE,
    LAB_TEMPLATE,
    LECTURE_TEMPLATE,
    MIDTERM_TEMPLATE,
    PROJECT_TEMPLATE,
    QUIZ_TEMPLATE,
    SYLLABUS_TEMPLATE,
)

# ---------------------------------------------------------------------------
# Document → source text file mapping
# ---------------------------------------------------------------------------

# Each entry maps a document to a .txt file in the uploads/files/ asset dir.
# The runner reads the file content and runs the full chain:
#   save_text_upload → create_upload → create_text_resource
#   → create_text_entry → create_text_upload → update_document

document_texts = [
    dict(
        document_id=HOMEWORK_TEMPLATE,
        source_file="text/240250e5-efb5-4d74-91b2-5484d0d9d0d9.txt",
    ),
    dict(
        document_id=LAB_TEMPLATE,
        source_file="text/1e2da365-fe6c-43ef-bf3a-3395fb281a09.txt",
    ),
    dict(
        document_id=LECTURE_TEMPLATE,
        source_file="text/c1464d2f-6fce-45b0-9c86-af40aad3df61.txt",
    ),
    dict(
        document_id=MIDTERM_TEMPLATE,
        source_file="text/d060952e-f68b-4a67-a231-1dd224937206.txt",
    ),
    dict(
        document_id=PROJECT_TEMPLATE,
        source_file="text/2d420b2a-a347-42e9-9e36-b1703d5a9aa3.txt",
    ),
    dict(
        document_id=QUIZ_TEMPLATE,
        source_file="text/f6f82c39-2db2-439b-9501-1124821f7c6c.txt",
    ),
    dict(
        document_id=SYLLABUS_TEMPLATE,
        source_file="text/c27ec685-ca41-445a-9f51-ea383b32df54.txt",
    ),
    dict(
        document_id=ACADEMIC_INTEGRITY_POLICY,
        source_file="text/5ac95858-9590-4164-b7d3-ca4285f1e0bf.txt",
    ),
]
