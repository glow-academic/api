"""Best-effort conversion of each PDF page to a base64 PNG data URL."""

import base64


def pdf_pages_to_image_data_urls(
    full_path: str,
    *,
    fitz_module: object | None = None,
) -> list[str]:
    """Best-effort conversion of each PDF page to a base64 PNG data URL.

    Tries PyMuPDF (fitz) if available. If unavailable or errors, returns [].
    """
    if fitz_module is None:
        try:  # Lazy import to avoid hard dependency
            import fitz as fitz_module  # type: ignore
        except Exception:
            return []

    image_urls: list[str] = []
    try:
        doc = fitz_module.open(full_path)
        for page in doc:
            pix = page.get_pixmap()
            png_bytes: bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode("ascii")
            image_urls.append(f"data:image/png;base64,{b64}")
        doc.close()
    except Exception:
        # If rendering fails, silently fallback to no images
        return []

    return image_urls
