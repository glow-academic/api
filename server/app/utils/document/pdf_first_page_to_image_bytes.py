"""Get first page of PDF as PNG image bytes."""


def pdf_first_page_to_image_bytes(
    full_path: str,
    *,
    fitz_module: object | None = None,
) -> bytes | None:
    """Get first page of PDF as PNG image bytes.

    Tries PyMuPDF (fitz) if available. If unavailable or errors, returns None.
    """
    if fitz_module is None:
        try:  # Lazy import to avoid hard dependency
            import fitz as fitz_module  # type: ignore
        except Exception:
            return None

    try:
        doc = fitz_module.open(full_path)
        if len(doc) == 0:
            doc.close()
            return None

        # Get first page
        page = doc[0]
        pix = page.get_pixmap()
        png_bytes: bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        # If rendering fails, return None
        return None
