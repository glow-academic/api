"""Theme derivation utilities for settings.

``ThemePrimitives`` carries the **essential 17** an org-admin needs to set
(plus 23 optional overrides for fine-tuning). ``derive_theme_tokens``
expands them into the full 40-token palette consumed by the client.

The 17 essentials, with the tokens each one drives:
  - ``background``    → card, popover (light only — dark elevates), border tones
  - ``primary``       → primary_foreground, sidebar_primary, *_foreground on accent surfaces (when accent is light)
  - ``accent``        → secondary, muted, sidebar_accent
  - ``card``          → popover (always tied), elevated surface in dark
  - ``sidebar``       → sidebar_foreground via foreground
  - ``muted_foreground``  hand-tuned mid-tone
  - ``ring``          → sidebar_ring
  - ``border``        → input, sidebar_border
  - ``destructive``   → danger
  - ``success``       (its _foreground hardcoded to near-white)
  - ``warning``       (its _foreground hardcoded to near-black)
  - ``info``          (its _foreground hardcoded to near-white)
  - ``chart1..5``     5 chart series colors

Everything else derives. Empty-in → empty-out: a token whose source
primitive is missing remains empty so ``globals.css`` defaults paint.
The other 23 fields (``foreground``, ``card_foreground``,
``secondary_foreground``, etc.) are still respected when explicitly set
— they win over derivation.
"""

from pydantic import BaseModel

# Standard text colors on chromatic backgrounds — invariant across themes.
# Status colors (success/error/info) are vibrant mid-tones designed to
# pair with white-ish text; warning (yellow) always pairs with dark text.
_LIGHT_TEXT = "oklch(0.985 0 0)"
_DARK_TEXT = "oklch(0.145 0 0)"
# Brand-on-brand text: the "soft dark" globals.css uses for
# primary_foreground when primary is a light tone (dark-mode pattern).
# Globally 0.205, picked to feel like a softer version of body text.
_SOFT_DARK_TEXT = "oklch(0.205 0 0)"


class ThemePrimitives(BaseModel):
    """40 optional fields. The 17 essentials drive the rest; the other 23
    are overrides for fine-tuning when derivation isn't what you want.

    Empty primitive → empty token → client falls back to globals.css.
    """

    # ── The Essential 17 ──
    background: str = ""
    primary: str = ""
    accent: str = ""
    card: str = ""
    sidebar: str = ""
    muted_foreground: str = ""
    ring: str = ""
    border: str = ""
    destructive: str = ""
    success: str = ""
    warning: str = ""
    info: str = ""
    chart1: str = ""
    chart2: str = ""
    chart3: str = ""
    chart4: str = ""
    chart5: str = ""

    # ── Optional overrides (auto-derived when empty) ──
    foreground: str = ""
    card_foreground: str = ""
    popover: str = ""
    popover_foreground: str = ""
    primary_foreground: str = ""
    secondary: str = ""
    secondary_foreground: str = ""
    muted: str = ""
    accent_foreground: str = ""
    destructive_foreground: str = ""
    danger: str = ""
    danger_foreground: str = ""
    input: str = ""
    success_foreground: str = ""
    warning_foreground: str = ""
    info_foreground: str = ""
    sidebar_foreground: str = ""
    sidebar_primary: str = ""
    sidebar_primary_foreground: str = ""
    sidebar_accent: str = ""
    sidebar_accent_foreground: str = ""
    sidebar_border: str = ""
    sidebar_ring: str = ""


class ThemeTokens(BaseModel):
    """40 fully-resolved CSS variable values (snake_case 1:1 with vars)."""

    background: str = ""
    foreground: str = ""
    card: str = ""
    card_foreground: str = ""
    popover: str = ""
    popover_foreground: str = ""
    primary: str = ""
    primary_foreground: str = ""
    secondary: str = ""
    secondary_foreground: str = ""
    muted: str = ""
    muted_foreground: str = ""
    accent: str = ""
    accent_foreground: str = ""
    destructive: str = ""
    destructive_foreground: str = ""
    danger: str = ""
    danger_foreground: str = ""
    border: str = ""
    input: str = ""
    ring: str = ""
    success: str = ""
    success_foreground: str = ""
    warning: str = ""
    warning_foreground: str = ""
    info: str = ""
    info_foreground: str = ""
    chart1: str = ""
    chart2: str = ""
    chart3: str = ""
    chart4: str = ""
    chart5: str = ""
    sidebar: str = ""
    sidebar_foreground: str = ""
    sidebar_primary: str = ""
    sidebar_primary_foreground: str = ""
    sidebar_accent: str = ""
    sidebar_accent_foreground: str = ""
    sidebar_border: str = ""
    sidebar_ring: str = ""


def derive_theme_tokens(primitives: ThemePrimitives) -> ThemeTokens:
    """Expand essentials into the full 40-token palette.

    Resolution order per field: explicit primitive → derived value →
    empty. Anything still empty falls through to globals.css.
    """
    from app.utils.theme.color_utils import ensure_contrast, parse_oklch
    from app.utils.theme.oklch_to_hex import hex_to_oklch

    def to_oklch(color: str) -> str:
        c = (color or "").strip()
        if not c:
            return ""
        if c.startswith("oklch("):
            return c
        h = c.lstrip("#")
        if len(h) != 6 or not all(ch in "0123456789ABCDEFabcdef" for ch in h):
            return ""
        return hex_to_oklch(f"#{h}")

    def pick(explicit: str, fallback: str) -> str:
        return explicit or fallback

    def lightness(c: str) -> float:
        try:
            return parse_oklch(c)[0]
        except Exception:
            return 0.5

    def is_light(c: str) -> bool:
        return bool(c) and lightness(c) > 0.5

    # Normalize all primitives to oklch
    p = {f: to_oklch(getattr(primitives, f)) for f in ThemePrimitives.model_fields}

    # === Surfaces ===
    background = p["background"]
    foreground = pick(p["foreground"], ensure_contrast(background, _DARK_TEXT) if background else "")
    card = pick(p["card"], background)
    popover = pick(p["popover"], card)
    sidebar = pick(p["sidebar"], card)

    # Foregrounds on background-tier surfaces always use `foreground`
    card_fg = pick(p["card_foreground"], foreground)
    popover_fg = pick(p["popover_foreground"], foreground)
    sidebar_fg = pick(p["sidebar_foreground"], foreground)

    # === Brand ===
    primary = p["primary"]
    # When primary is light (dark-theme pattern), text is soft-dark
    # (0.205) — matches globals' --primary-foreground in .dark. When
    # primary is dark (light-theme pattern), text is near-white (0.985).
    primary_fg_default = _SOFT_DARK_TEXT if is_light(primary) else _LIGHT_TEXT
    primary_fg = pick(p["primary_foreground"], primary_fg_default if primary else "")

    accent = p["accent"]
    # Accent / secondary / muted are the same neutral-elevated tone.
    secondary = pick(p["secondary"], accent)
    muted = pick(p["muted"], accent)
    sidebar_accent = pick(p["sidebar_accent"], accent)

    # Foreground on accent-tier surfaces:
    #   - When accent is light (light theme), use `primary` (a soft dark
    #     that matches globals' 0.205, not the body text 0.145).
    #   - When accent is dark (dark theme), use `foreground` (near-white,
    #     same as body text).
    accent_fg_default = primary if is_light(accent) else foreground
    accent_fg = pick(p["accent_foreground"], accent_fg_default)
    secondary_fg = pick(p["secondary_foreground"], accent_fg_default)
    sidebar_accent_fg = pick(p["sidebar_accent_foreground"], accent_fg_default)

    # === Sidebar primary (mirrors primary unless overridden) ===
    # Sidebar_primary can be a different hue from `primary` (globals
    # uses a blue accent for dark-mode sidebar nav), so derive its
    # foreground from sidebar_primary itself, not from primary_fg.
    sidebar_primary = pick(p["sidebar_primary"], primary)
    sidebar_primary_fg_default = (
        _SOFT_DARK_TEXT if is_light(sidebar_primary) else _LIGHT_TEXT
    )
    sidebar_primary_fg = pick(
        p["sidebar_primary_foreground"],
        sidebar_primary_fg_default if sidebar_primary else "",
    )

    # === Status — chromatic colors with fixed text-color pairings ===
    # White text on saturated success/error/info; dark text on yellow.
    destructive = p["destructive"]
    destructive_fg = pick(p["destructive_foreground"], _LIGHT_TEXT if destructive else "")
    danger = pick(p["danger"], destructive)
    danger_fg = pick(p["danger_foreground"], _LIGHT_TEXT if danger else "")

    success = p["success"]
    success_fg = pick(p["success_foreground"], _LIGHT_TEXT if success else "")
    warning = p["warning"]
    warning_fg = pick(p["warning_foreground"], _DARK_TEXT if warning else "")
    info = p["info"]
    info_fg = pick(p["info_foreground"], _LIGHT_TEXT if info else "")

    # === Borders / inputs / ring ===
    border = p["border"]
    input_ = pick(p["input"], border)
    sidebar_border = pick(p["sidebar_border"], border)
    ring = p["ring"]
    sidebar_ring = pick(p["sidebar_ring"], ring)

    # === Hand-tuned ===
    muted_fg = p["muted_foreground"]

    return ThemeTokens(
        background=background,
        foreground=foreground,
        card=card,
        card_foreground=card_fg,
        popover=popover,
        popover_foreground=popover_fg,
        primary=primary,
        primary_foreground=primary_fg,
        secondary=secondary,
        secondary_foreground=secondary_fg,
        muted=muted,
        muted_foreground=muted_fg,
        accent=accent,
        accent_foreground=accent_fg,
        destructive=destructive,
        destructive_foreground=destructive_fg,
        danger=danger,
        danger_foreground=danger_fg,
        border=border,
        input=input_,
        ring=ring,
        success=success,
        success_foreground=success_fg,
        warning=warning,
        warning_foreground=warning_fg,
        info=info,
        info_foreground=info_fg,
        chart1=p["chart1"],
        chart2=p["chart2"],
        chart3=p["chart3"],
        chart4=p["chart4"],
        chart5=p["chart5"],
        sidebar=sidebar,
        sidebar_foreground=sidebar_fg,
        sidebar_primary=sidebar_primary,
        sidebar_primary_foreground=sidebar_primary_fg,
        sidebar_accent=sidebar_accent,
        sidebar_accent_foreground=sidebar_accent_fg,
        sidebar_border=sidebar_border,
        sidebar_ring=sidebar_ring,
    )
