"""Color utility functions for theme derivation."""

import re


def parse_oklch(oklch_str: str) -> tuple[float, float, float, float | None]:
    """
    Parse oklch color string into components.
    Handles both 'oklch(L C H)' and 'oklch(L C H / alpha)' formats.

    Returns: (lightness, chroma, hue, alpha)
    """
    # Match oklch(L C H) or oklch(L C H / alpha)
    match = re.match(
        r"oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+%?))?\)", oklch_str
    )
    if not match:
        raise ValueError(f"Invalid oklch format: {oklch_str}")

    lightness = float(match.group(1))
    chroma = float(match.group(2))
    hue = float(match.group(3))
    alpha = None
    if match.group(4):
        alpha_str = match.group(4).rstrip("%")
        alpha = float(alpha_str)
        if "%" in match.group(4):
            alpha = alpha / 100.0

    return (lightness, chroma, hue, alpha)


def format_oklch(
    lightness: float, chroma: float, hue: float, alpha: float | None = None
) -> str:
    """Format oklch components into string."""
    if alpha is not None:
        return f"oklch({lightness} {chroma} {hue} / {alpha})"
    return f"oklch({lightness} {chroma} {hue})"


def tint(color: str, amount: float) -> str:
    """
    Lighten a color by moving lightness towards 1.0 (white).
    amount: 0.0 = no change, 1.0 = pure white
    """
    l, c, h, alpha = parse_oklch(color)
    # Move lightness towards 1.0
    new_l = l + (1.0 - l) * amount
    # Reduce chroma as we lighten (colors become less saturated)
    new_c = c * (1.0 - amount * 0.5)
    return format_oklch(new_l, new_c, h, alpha)


def shade(color: str, amount: float) -> str:
    """
    Darken a color by moving lightness towards 0.0 (black).
    amount: 0.0 = no change, 1.0 = pure black
    """
    l, c, h, alpha = parse_oklch(color)
    # Move lightness towards 0.0
    new_l = l * (1.0 - amount)
    # Slightly increase chroma as we darken (for richer darks)
    new_c = c * (1.0 + amount * 0.1)
    return format_oklch(new_l, new_c, h, alpha)


def ensure_contrast(background: str, candidate: str) -> str:
    """
    Ensure text color has sufficient contrast against background.
    Simple implementation: if background is light, use dark text; if dark, use light text.
    """
    bg_l, _, _, _ = parse_oklch(background)
    cand_l, cand_c, cand_h, cand_alpha = parse_oklch(candidate)

    # If background is light (L > 0.5), ensure text is dark (L < 0.3)
    # If background is dark (L < 0.5), ensure text is light (L > 0.7)
    if bg_l > 0.5:
        # Light background - use dark text
        if cand_l > 0.3:
            cand_l = 0.145  # Dark text
            cand_c = 0  # No chroma for pure dark
            cand_h = 0  # No hue for pure dark
    else:
        # Dark background - use light text
        if cand_l < 0.7:
            cand_l = 0.985  # Light text
            cand_c = 0  # No chroma for pure light
            cand_h = 0  # No hue for pure light

    return format_oklch(cand_l, cand_c, cand_h, cand_alpha)
