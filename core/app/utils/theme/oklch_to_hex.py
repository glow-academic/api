"""Convert oklch colors to hex for color picker compatibility."""

import math
import re


def parse_oklch(oklch_str: str) -> tuple[float, float, float]:
    """Parse oklch color string into (L, C, H) components."""
    match = re.match(
        r"oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*[\d.]+%?)?\)", oklch_str
    )
    if not match:
        raise ValueError(f"Invalid oklch format: {oklch_str}")

    return (float(match.group(1)), float(match.group(2)), float(match.group(3)))


def oklch_to_hex(oklch_str: str) -> str:
    """
    Convert oklch color to hex format.

    Algorithm:
    1. oklch -> oklab (convert polar to rectangular)
    2. oklab -> linear RGB (matrix transformation)
    3. linear RGB -> sRGB (gamma correction)
    4. sRGB -> hex
    """
    L, C, H = parse_oklch(oklch_str)

    # Convert hue from degrees to radians
    h_rad = math.radians(H)

    # Convert oklch to oklab (polar to rectangular)
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)

    # OKLab to linear RGB matrix (inverse of linear RGB to OKLab)
    # This is the inverse of the OKLab transformation matrix
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    # Apply non-linearity
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_

    # Linear RGB to sRGB matrix (inverse of sRGB to linear RGB)
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    # Gamma correction (linear RGB to sRGB)
    def gamma_correct(val: float) -> float:
        if val <= 0.0031308:
            return 12.92 * val
        power: float = val ** (1.0 / 2.4)
        return 1.055 * power - 0.055

    r_srgb = gamma_correct(r)
    g_srgb = gamma_correct(g)
    b_srgb = gamma_correct(bl)

    # Clamp to [0, 1] and convert to [0, 255]
    r_int = max(0, min(255, int(round(r_srgb * 255))))
    g_int = max(0, min(255, int(round(g_srgb * 255))))
    b_int = max(0, min(255, int(round(b_srgb * 255))))

    # Convert to hex
    return f"#{r_int:02x}{g_int:02x}{b_int:02x}"


def hex_to_oklch(hex_str: str) -> str:
    """
    Convert hex color to oklch format (for verification).
    This is a simplified version - full conversion would require
    sRGB -> linear RGB -> OKLab -> OKLCH
    """
    # Remove # if present
    hex_clean = hex_str.lstrip("#")

    # Parse RGB
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0

    # Gamma correction (sRGB to linear RGB)
    def inv_gamma_correct(val: float) -> float:
        if val <= 0.04045:
            return val / 12.92
        ratio: float = (val + 0.055) / 1.055
        power: float = ratio**2.4
        return power

    r_lin = inv_gamma_correct(r)
    g_lin = inv_gamma_correct(g)
    b_lin = inv_gamma_correct(b)

    # Linear RGB to OKLab matrix
    l_ = 0.4122214708 * r_lin + 0.5363325363 * g_lin + 0.0514459929 * b_lin
    m_ = 0.2119034982 * r_lin + 0.6806995451 * g_lin + 0.1073969566 * b_lin
    s_ = 0.0883024619 * r_lin + 0.2817188376 * g_lin + 0.6299787005 * b_lin

    # Apply non-linearity
    l_cbrt = l_ ** (1.0 / 3.0) if l_ > 0 else 0
    m_cbrt = m_ ** (1.0 / 3.0) if m_ > 0 else 0
    s_cbrt = s_ ** (1.0 / 3.0) if s_ > 0 else 0

    # OKLab
    L = 0.2104542553 * l_cbrt + 0.7936177850 * m_cbrt - 0.0040720468 * s_cbrt
    a = 1.9779984951 * l_cbrt - 2.4285922050 * m_cbrt + 0.4505937099 * s_cbrt
    b_lab = 0.0259040371 * l_cbrt + 0.7827717662 * m_cbrt - 0.8086757660 * s_cbrt

    # OKLab to OKLCH (rectangular to polar)
    C = math.sqrt(a * a + b_lab * b_lab)
    H = math.degrees(math.atan2(b_lab, a))
    if H < 0:
        H += 360

    return f"oklch({L:.3f} {C:.3f} {H:.1f})"
