"""Server-side sanitizer for icon ``value`` strings (stored XSS defence).

An ``icons_resource.value`` is rendered verbatim by the client ``SvgIcon``
component, which treats a value beginning with ``<svg`` as *raw inline SVG
markup* and injects it into the DOM (other values are looked up as a named
icon). Any authenticated persona/artifact author can store an icon value,
so an unsanitized value lets a caller persist malicious SVG
(``<svg onload=...>``, ``<script>``, ``<img onerror=...>``,
``<foreignObject>``, ``javascript:`` / external ``href``) that then executes
in *other* users' surfaces — a stored XSS.

The client now render-sanitizes via DOMPurify, which closes execution. This
module is the complementary write-side defence: it stops the malicious
payload being persisted in the first place. It is applied at the single
write boundary (``create_icon``), so every path that stores an icon value is
covered.

Approach (NOT a regex blocklist — those are bypassable): inline SVG is the
legitimate shape, so raw SVG is *sanitized* (not rejected) by parsing with
``lxml`` and rebuilding it from a conservative allowlist of safe SVG
elements / attributes — dropping scripting elements, event-handler
attributes, ``style``, and non-fragment / ``javascript:`` references. Plain
named identifiers (no markup) pass through untouched. Markup that contains
no ``<svg>`` root is rejected (``ValueError`` → HTTP 400) since it is
neither a valid name nor a valid icon SVG.
"""

from __future__ import annotations

from lxml import etree  # type: ignore

# Safe, presentational SVG elements (lowercased local names). Notably absent:
# script, foreignObject, image, animate*, set, a, iframe, style, etc.
_ALLOWED_TAGS = {
    "svg",
    "g",
    "path",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "rect",
    "defs",
    "title",
    "desc",
    "lineargradient",
    "radialgradient",
    "stop",
    "clippath",
    "mask",
    "pattern",
    "symbol",
    "use",
    "text",
    "tspan",
    "marker",
}

# Safe attributes (lowercased local names). No event handlers (on*), no
# ``style`` (can carry url()/expression), no scripting hooks.
_ALLOWED_ATTRS = {
    "width",
    "height",
    "viewbox",
    "xmlns",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-opacity",
    "stroke-miterlimit",
    "d",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "x",
    "y",
    "x1",
    "x2",
    "y1",
    "y2",
    "points",
    "transform",
    "opacity",
    "fill-opacity",
    "fill-rule",
    "clip-rule",
    "class",
    "id",
    "gradientunits",
    "gradienttransform",
    "spreadmethod",
    "offset",
    "stop-color",
    "stop-opacity",
    "clip-path",
    "mask",
    "vector-effect",
    "preserveaspectratio",
    "aria-hidden",
    "aria-label",
    "role",
    "focusable",
    "version",
}

_SVG_NS = "http://www.w3.org/2000/svg"


def _local(name: str) -> str:
    """Lowercased local name, stripping any ``{namespace}`` prefix."""
    return name.split("}")[-1].lower()


def _clean_element(el: etree._Element) -> None:
    """Recursively strip disallowed children/attributes from ``el`` in place."""
    for child in list(el):
        tag = child.tag
        # Comments / processing instructions (non-str tag) — drop them.
        if not isinstance(tag, str) or _local(tag) not in _ALLOWED_TAGS:
            el.remove(child)
            continue
        _clean_element(child)

    for name, value in list(el.attrib.items()):
        ln = _local(name)
        if ln.startswith("on"):  # event handlers: onload, onerror, ...
            del el.attrib[name]
        elif ln == "href":  # xlink:href / href — only internal fragments
            if not value.strip().startswith("#"):
                del el.attrib[name]
        elif ln == "style":  # can carry url()/expression — drop entirely
            del el.attrib[name]
        elif ln not in _ALLOWED_ATTRS:
            del el.attrib[name]


def sanitize_icon_value(value: str) -> str:
    """Return a safe-to-store icon ``value``.

    - A plain named identifier (no markup, no ``<``) is returned stripped,
      unchanged.
    - Raw SVG markup is parsed and rebuilt from a safe allowlist; the first
      ``<svg>`` subtree is kept and re-serialized, dropping any sibling
      markup (e.g. a trailing ``<img onerror=...>``), scripting elements,
      event-handler attributes, and unsafe references.

    Raises:
        ValueError: if the value is empty, or contains markup but no
            parseable ``<svg>`` root (neither a valid name nor a valid icon).
    """
    if value is None or not value.strip():
        raise ValueError("Icon value must not be empty")

    stripped = value.strip()

    # No markup at all → a named identifier (e.g. "robot"). Safe as-is.
    if "<" not in stripped:
        return stripped

    # Wrap so multiple/namespaced top-level nodes parse under one root and
    # xlink: prefixes resolve. resolve_entities=False + no_network=True guard
    # against entity-expansion / external-entity (XXE) attacks.
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )
    wrapped = (
        '<__icon_wrap__ xmlns:xlink="http://www.w3.org/1999/xlink">'
        f"{stripped}</__icon_wrap__>"
    )
    try:
        root = etree.fromstring(wrapped.encode("utf-8"), parser)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Icon value is not valid SVG markup: {exc}") from None

    svg = next((el for el in root.iter() if _local(el.tag) == "svg"), None)
    if svg is None:
        raise ValueError("Icon value markup must be an <svg> element")

    _clean_element(svg)
    return etree.tostring(svg, encoding="unicode")
