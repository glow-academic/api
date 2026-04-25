"""Organization color theme seed definitions.

Colors are resource-level creates (no artifact wrapper).
They get linked to the setting via color_ids.
"""

from database.seeds.ids import sid

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

C_PRIMARY = sid("org/color/primary")
C_ACCENT = sid("org/color/accent")
C_SUCCESS = sid("org/color/success")
C_WARNING = sid("org/color/warning")
C_ERROR = sid("org/color/error")
C_SIDEBAR_BG = sid("org/color/sidebar-background")
C_SIDEBAR_PRIMARY = sid("org/color/sidebar-primary")
C_CHART_2 = sid("org/color/chart2")
C_CHART_4 = sid("org/color/chart4")
C_CHART_5 = sid("org/color/chart5")

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
    dict(id=C_PRIMARY, name="Custom", description="Custom color", hex_code="#171717", type="primary"),
    dict(id=C_ACCENT, name="Custom", description="Custom color", hex_code="#f5f5f5", type="accent"),
    dict(id=C_SUCCESS, name="Custom", description="Custom color", hex_code="#009e34", type="success"),
    dict(id=C_WARNING, name="Custom", description="Custom color", hex_code="#ea8100", type="warning"),
    dict(id=C_ERROR, name="Custom", description="Custom color", hex_code="#e7000b", type="danger"),
    dict(id=C_SIDEBAR_BG, name="Custom", description="Custom color", hex_code="#fafafa", type="background"),
    dict(id=C_SIDEBAR_PRIMARY, name="Custom", description="Custom color", hex_code="#171717", type="foreground"),
    dict(id=C_CHART_2, name="Custom", description="Custom color", hex_code="#404040", type="chart2"),
    dict(id=C_CHART_4, name="Custom", description="Custom color", hex_code="#b0b0b0", type="chart4"),
    dict(id=C_CHART_5, name="Custom", description="Custom color", hex_code="#e0e0e0", type="chart5"),
]
