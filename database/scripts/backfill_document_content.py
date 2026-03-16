#!/usr/bin/env python3
"""
Backfill text and page images for PDF-based documents.

For each document with an upload (PDF) but no text:
  1. Extract text from PDF using pypdf → texts_entry + texts_resource + texts_texts_connection
  2. Render each page as PNG using pymupdf → uploads_entry + uploads_resource +
     uploads_uploads_connection + images_resource + document_images_junction
  3. Update documents_resource.text_id and image_ids

Usage:
    python backfill_document_content.py          # Run backfill
    python backfill_document_content.py --dry-run # Preview without changes
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
DB_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = DB_DIR.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"
IMAGES_DIR = UPLOADS_DIR / "image"

env_file = DB_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DB_USER = os.environ.get("DB_USER", "myuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "mypassword")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "mydb")

DRY_RUN = "--dry-run" in sys.argv


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------


def extract_text_pages(pdf_path: str) -> list[str]:
    """Extract text per page from a PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return pages


def render_pages_as_png(
    pdf_path: str, output_dir: Path, slug: str
) -> list[tuple[str, bytes]]:
    """Render each PDF page as PNG. Returns list of (relative_path, png_bytes)."""
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap()
        png_bytes = pix.tobytes("png")
        rel_path = f"image/{slug}-page{page_num + 1}.png"
        results.append((rel_path, png_bytes))
    doc.close()
    return results


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------


async def backfill(conn: asyncpg.Connection) -> None:
    """Backfill text and images for PDF documents."""

    # Find documents with upload but no text
    rows = await conn.fetch("""
        SELECT dr.id AS doc_res_id, dr.name, dr.upload_id,
               ddj.document_id AS artifact_id,
               ue.file_path
        FROM documents_resource dr
        JOIN document_documents_junction ddj ON ddj.documents_id = dr.id
        JOIN uploads_resource ur ON ur.id = dr.upload_id
        JOIN uploads_uploads_connection uuc ON uuc.uploads_id = ur.id
        JOIN uploads_entry ue ON ue.id = uuc.upload_id
        WHERE dr.upload_id IS NOT NULL
          AND dr.text_id IS NULL
        ORDER BY dr.name
    """)

    if not rows:
        print("No documents to backfill.")
        return

    print(f"Found {len(rows)} PDF documents to backfill.\n")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    for r in rows:
        doc_res_id = r["doc_res_id"]
        doc_name = r["name"]
        artifact_id = r["artifact_id"]
        file_path = r["file_path"]
        full_path = str(UPLOADS_DIR / file_path)

        if not os.path.exists(full_path):
            print(f"  SKIP {doc_name}: file not found at {full_path}")
            continue

        print(f"  Processing: {doc_name} ({file_path})")

        # --- Text extraction ---
        text_pages = extract_text_pages(full_path)
        full_text = "\n\n".join(text_pages)

        if DRY_RUN:
            print(f"    Text: {len(full_text)} chars across {len(text_pages)} pages")
        else:
            # Create texts_entry (reuse if same content already exists)
            import hashlib

            content_hash = hashlib.md5(full_text.encode()).hexdigest()
            text_entry_id = await conn.fetchval(
                """
                SELECT id FROM texts_entry WHERE content_hash = $1
            """,
                content_hash,
            )
            if text_entry_id is None:
                text_entry_id = await conn.fetchval(
                    """
                    INSERT INTO texts_entry (content, active, generated, mcp)
                    VALUES ($1, true, false, false)
                    RETURNING id
                """,
                    full_text,
                )
            else:
                print(f"    Text: reusing existing texts_entry={text_entry_id}")

            # Create texts_resource with denormalized text_id
            text_res_id = await conn.fetchval(
                """
                INSERT INTO texts_resource (active, generated, mcp, text_id)
                VALUES (true, false, false, $1)
                RETURNING id
            """,
                text_entry_id,
            )

            # Create texts_texts_connection
            await conn.execute(
                """
                INSERT INTO texts_texts_connection (texts_id, text_id, active)
                VALUES ($1, $2, true)
                ON CONFLICT (texts_id, text_id) DO NOTHING
            """,
                text_res_id,
                text_entry_id,
            )

            # Create document_texts_junction
            await conn.execute(
                """
                INSERT INTO document_texts_junction (document_id, texts_id, active)
                VALUES ($1, $2, true)
                ON CONFLICT (document_id, texts_id) DO NOTHING
            """,
                artifact_id,
                text_res_id,
            )

            # Update documents_resource.text_id
            await conn.execute(
                """
                UPDATE documents_resource SET text_id = $1 WHERE id = $2
            """,
                text_res_id,
                doc_res_id,
            )

            print(f"    Text: {len(full_text)} chars -> texts_entry={text_entry_id}")

        # --- Page images ---
        slug = doc_name.lower().replace(" ", "-").replace(".pdf", "")
        page_images = render_pages_as_png(full_path, IMAGES_DIR, slug)

        if DRY_RUN:
            print(f"    Images: {len(page_images)} pages")
            for rel_path, png_bytes in page_images:
                print(f"      {rel_path} ({len(png_bytes):,} bytes)")
        else:
            image_ids = []
            for page_num, (rel_path, png_bytes) in enumerate(page_images, 1):
                # Save PNG file
                out_path = UPLOADS_DIR / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(png_bytes)

                # Create uploads_entry for the image file
                upload_entry_id = await conn.fetchval(
                    """
                    INSERT INTO uploads_entry (file_path, mime_type, size, active, generated, mcp)
                    VALUES ($1, 'image/png', $2, true, false, false)
                    RETURNING id
                """,
                    rel_path,
                    len(png_bytes),
                )

                # Create uploads_resource (wraps the entry)
                upload_res_id = await conn.fetchval(
                    """
                    INSERT INTO uploads_resource (active, generated, mcp, upload_id)
                    VALUES (true, false, false, $1)
                    RETURNING id
                """,
                    upload_entry_id,
                )

                # Create uploads_uploads_connection (links resource ↔ entry)
                await conn.execute(
                    """
                    INSERT INTO uploads_uploads_connection (uploads_id, upload_id, active)
                    VALUES ($1, $2, true)
                    ON CONFLICT (uploads_id, upload_id) DO NOTHING
                """,
                    upload_res_id,
                    upload_entry_id,
                )

                # Create images_resource (upload_id → uploads_resource)
                img_name = f"{doc_name} Page {page_num}"
                image_res_id = await conn.fetchval(
                    """
                    INSERT INTO images_resource (name, description, upload_id, completed, active, generated, mcp)
                    VALUES ($1, $1, $2, true, true, false, false)
                    RETURNING id
                """,
                    img_name,
                    upload_res_id,
                )

                # Create document_images_junction
                await conn.execute(
                    """
                    INSERT INTO document_images_junction (document_id, images_id, active)
                    VALUES ($1, $2, true)
                    ON CONFLICT (document_id, images_id) DO NOTHING
                """,
                    artifact_id,
                    image_res_id,
                )

                image_ids.append(image_res_id)

            # Update documents_resource.image_ids
            await conn.execute(
                """
                UPDATE documents_resource SET image_ids = $1 WHERE id = $2
            """,
                image_ids,
                doc_res_id,
            )

            print(f"    Images: {len(image_ids)} pages saved to uploads/image/")

    print("\nBackfill complete.")


async def main() -> None:
    if DRY_RUN:
        print("=== DRY RUN (no changes will be made) ===\n")

    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    try:
        if DRY_RUN:
            await backfill(conn)
        else:
            async with conn.transaction():
                await backfill(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
