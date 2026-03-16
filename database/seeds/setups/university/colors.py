"""University color theme seed definitions.

Colors are resource-level creates (no artifact wrapper).
They get linked to the setting via post_links.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

C_PRIMARY = sid("uni/color/primary")
C_ACCENT = sid("uni/color/accent")
C_SUCCESS = sid("uni/color/success")
C_WARNING = sid("uni/color/warning")
C_ERROR = sid("uni/color/error")
C_SIDEBAR_BG = sid("uni/color/sidebar-background")
C_SIDEBAR_PRIMARY = sid("uni/color/sidebar-primary")
C_CHART_2 = sid("uni/color/chart2")
C_CHART_4 = sid("uni/color/chart4")
C_CHART_5 = sid("uni/color/chart5")

ALL_COLOR_IDS = [
    C_PRIMARY,
    C_ACCENT,
    C_SUCCESS,
    C_WARNING,
    C_ERROR,
    C_SIDEBAR_BG,
    C_SIDEBAR_PRIMARY,
    C_CHART_2,
    C_CHART_4,
    C_CHART_5,
]

# ---------------------------------------------------------------------------
# Color definitions
# ---------------------------------------------------------------------------

colors = [
    dict(id=C_PRIMARY, name="Custom", description="Custom color", hex_code="#171717"),
    dict(id=C_ACCENT, name="Custom", description="Custom color", hex_code="#f5f5f5"),
    dict(id=C_SUCCESS, name="Custom", description="Custom color", hex_code="#009e34"),
    dict(id=C_WARNING, name="Custom", description="Custom color", hex_code="#ea8100"),
    dict(id=C_ERROR, name="Custom", description="Custom color", hex_code="#e7000b"),
    dict(
        id=C_SIDEBAR_BG, name="Custom", description="Custom color", hex_code="#fafafa"
    ),
    dict(
        id=C_SIDEBAR_PRIMARY,
        name="Custom",
        description="Custom color",
        hex_code="#171717",
    ),
    dict(id=C_CHART_2, name="Custom", description="Custom color", hex_code="#404040"),
    dict(id=C_CHART_4, name="Custom", description="Custom color", hex_code="#b0b0b0"),
    dict(id=C_CHART_5, name="Custom", description="Custom color", hex_code="#e0e0e0"),
]
