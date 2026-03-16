"""Theme derivation utilities for settings.

This module provides functions to derive full ThemeTokens from user-editable ThemePrimitives.
These functions are used across multiple endpoints (documents, scenarios, etc.) for consistent
theme handling.
"""

from pydantic import BaseModel


class ThemePrimitives(BaseModel):
    """User-editable theme color primitives.

    These are the colors that users can edit in the settings UI.
    Colors can be in hex (#RRGGBB) or oklch format.
    """

    primary: str = ""
    accent: str = ""
    background: str = ""
    surface: str = ""
    success: str = ""
    warning: str = ""
    error: str = ""
    sidebarBackground: str = ""
    sidebarPrimary: str = ""
    chart1: str = ""
    chart2: str = ""
    chart3: str = ""
    chart4: str = ""
    chart5: str = ""


class ThemeTokens(BaseModel):
    """Full internal design tokens derived from ThemePrimitives.

    These are the computed theme values used throughout the application.
    All colors are in oklch format for consistency.
    """

    background: str = ""
    foreground: str = ""
    card: str = ""
    cardForeground: str = ""
    popover: str = ""
    popoverForeground: str = ""
    primary: str = ""
    primaryForeground: str = ""
    secondary: str = ""
    secondaryForeground: str = ""
    muted: str = ""
    mutedForeground: str = ""
    accent: str = ""
    accentForeground: str = ""
    destructive: str = ""
    border: str = ""
    input: str = ""
    ring: str = ""
    success: str = ""
    successForeground: str = ""
    warning: str = ""
    warningForeground: str = ""
    info: str = ""
    infoForeground: str = ""
    chart1: str = ""
    chart2: str = ""
    chart3: str = ""
    chart4: str = ""
    chart5: str = ""
    sidebar: str = ""
    sidebarForeground: str = ""
    sidebarPrimary: str = ""
    sidebarPrimaryForeground: str = ""
    sidebarAccent: str = ""
    sidebarAccentForeground: str = ""
    sidebarBorder: str = ""
    sidebarRing: str = ""


def derive_theme_tokens(primitives: ThemePrimitives) -> ThemeTokens:
    """Derive full ThemeTokens from user-editable ThemePrimitives.

    This function performs complex color math to derive all theme tokens
    from the user-editable primitives. It handles contrast calculations,
    color tinting/shading, and ensures accessibility.

    Args:
        primitives: User-editable theme primitives

    Returns:
        Full ThemeTokens object with all derived colors
    """
    # Import color utilities (same as profile/context.py)
    from app.utils.theme.color_utils import ensure_contrast, shade, tint
    from app.utils.theme.oklch_to_hex import hex_to_oklch

    def normalize_color_to_oklch(color: str) -> str:
        """Normalize color input to oklch format."""
        color_trimmed = color.strip()
        if not color_trimmed:
            return "oklch(0.5 0 0)"  # Default gray

        if color_trimmed.startswith("oklch("):
            return color_trimmed

        hex_clean = color_trimmed.lstrip("#")
        if len(hex_clean) != 6 or not all(
            c in "0123456789ABCDEFabcdef" for c in hex_clean
        ):
            return "oklch(0.5 0 0)"  # Default gray

        return hex_to_oklch(f"#{hex_clean}")

    # Normalize all color inputs to oklch format
    background = normalize_color_to_oklch(primitives.background or "")
    surface = normalize_color_to_oklch(primitives.surface or "")
    primary = normalize_color_to_oklch(primitives.primary or "")
    accent = normalize_color_to_oklch(primitives.accent or "")
    sidebar_bg = normalize_color_to_oklch(primitives.sidebarBackground or "")
    sidebar_primary = normalize_color_to_oklch(primitives.sidebarPrimary or "")
    success = normalize_color_to_oklch(primitives.success or "")
    warning = normalize_color_to_oklch(primitives.warning or "")
    error = normalize_color_to_oklch(primitives.error or "")

    # Foregrounds based on contrast
    foreground = ensure_contrast(background, "oklch(0.145 0 0)")
    primary_fg = ensure_contrast(primary, "oklch(0.985 0 0)")
    accent_fg = ensure_contrast(accent, "oklch(0.205 0 0)")
    surface_fg = ensure_contrast(surface, foreground)

    # Status foregrounds
    success_fg = ensure_contrast(success, "oklch(0.985 0 0)")
    warning_fg = ensure_contrast(warning, "oklch(0.145 0 0)")
    error_fg = ensure_contrast(error, "oklch(0.985 0 0)")

    # Info derived from primary
    info_color = tint(primary, 0.05)
    info_fg = ensure_contrast(info_color, foreground)

    # Derived colors
    muted_color = shade(background, 0.03)
    muted_fg = shade(foreground, 0.2)
    border_color = shade(background, 0.078)
    input_color = shade(background, 0.078)
    ring_color = shade(primary, 0.05)

    # Sidebar derived colors
    sidebar_fg = ensure_contrast(sidebar_bg, surface_fg)
    sidebar_primary_fg = ensure_contrast(sidebar_primary, surface_fg)
    sidebar_accent = shade(sidebar_bg, 0.015)
    sidebar_accent_fg = ensure_contrast(sidebar_accent, surface_fg)
    sidebar_border = shade(sidebar_bg, 0.064)
    sidebar_ring = shade(sidebar_primary, 0.05)

    # Card colors (derived from surface)
    card = surface
    card_fg = surface_fg
    popover = surface
    popover_fg = surface_fg

    # Secondary colors (derived from muted)
    secondary = muted_color
    secondary_fg = muted_fg

    # Destructive (derived from error)
    destructive = error
    destructive_fg = error_fg

    # Chart colors
    chart1 = normalize_color_to_oklch(primitives.chart1 or "")
    chart2 = normalize_color_to_oklch(primitives.chart2 or "")
    chart3 = normalize_color_to_oklch(primitives.chart3 or "")
    chart4 = normalize_color_to_oklch(primitives.chart4 or "")
    chart5 = normalize_color_to_oklch(primitives.chart5 or "")

    return ThemeTokens(
        background=background,
        foreground=foreground,
        card=card,
        cardForeground=card_fg,
        popover=popover,
        popoverForeground=popover_fg,
        primary=primary,
        primaryForeground=primary_fg,
        secondary=secondary,
        secondaryForeground=secondary_fg,
        muted=muted_color,
        mutedForeground=muted_fg,
        accent=accent,
        accentForeground=accent_fg,
        destructive=destructive,
        border=border_color,
        input=input_color,
        ring=ring_color,
        success=success,
        successForeground=success_fg,
        warning=warning,
        warningForeground=warning_fg,
        info=info_color,
        infoForeground=info_fg,
        chart1=chart1,
        chart2=chart2,
        chart3=chart3,
        chart4=chart4,
        chart5=chart5,
        sidebar=sidebar_bg,
        sidebarForeground=sidebar_fg,
        sidebarPrimary=sidebar_primary,
        sidebarPrimaryForeground=sidebar_primary_fg,
        sidebarAccent=sidebar_accent,
        sidebarAccentForeground=sidebar_accent_fg,
        sidebarBorder=sidebar_border,
        sidebarRing=sidebar_ring,
    )
