"""Organization color theme — the Essential 18 per palette.

Each row's ``type`` is the canonical CSS-variable name (snake_case,
optionally ``dark_``-prefixed). Hex codes are computed from the oklch
values in ``learnloopllc-glow-client/app/globals.css`` so the seeded
theme reproduces the unthemed page within hex↔oklch rounding (visually
identical) in both light and dark modes.

The 18 essentials cover everything the client paints; the other 22
tokens (``foreground``, ``card_foreground``, ``secondary``, …) are
derived inside ``derive_theme_tokens``. Setting any one of those 22
explicitly will still override the derivation — sparse seeds Just Work.

Light palette (17):       background, primary, accent, card, sidebar,
                          muted_foreground, ring, border, destructive,
                          success, warning, info, chart1..5.
Dark palette (18):        the same 17 + sidebar_primary (which diverges
                          from primary in dark mode — globals uses a
                          blue accent rather than the gray primary).
"""

from database.seeds.ids import sid

_LIGHT: list[tuple[str, str]] = [
    ("background",       "#ffffff"),
    ("primary",          "#171717"),
    ("accent",           "#f5f5f5"),
    ("card",             "#ffffff"),
    ("sidebar",          "#fafafa"),
    ("muted_foreground", "#737373"),
    ("ring",             "#a1a1a1"),
    ("border",           "#e5e5e5"),
    ("destructive",      "#e7000b"),
    ("success",          "#009e34"),
    ("warning",          "#ea8100"),
    ("info",             "#0065b4"),
    ("chart1",           "#f54900"),
    ("chart2",           "#009689"),
    ("chart3",           "#104e64"),
    ("chart4",           "#ffb900"),
    ("chart5",           "#fe9a00"),
]

_DARK: list[tuple[str, str]] = [
    ("dark_background",       "#0a0a0a"),
    ("dark_primary",          "#e5e5e5"),
    ("dark_accent",           "#262626"),
    ("dark_card",             "#171717"),
    ("dark_sidebar",          "#171717"),
    ("dark_sidebar_primary",  "#1447e6"),   # diverges from dark_primary
    ("dark_muted_foreground", "#a1a1a1"),
    ("dark_ring",             "#737373"),
    ("dark_border",           "#262626"),
    ("dark_destructive",      "#ff6467"),
    ("dark_success",          "#009e34"),
    ("dark_warning",          "#ea8100"),
    ("dark_info",             "#0065b4"),
    ("dark_chart1",           "#1447e6"),
    ("dark_chart2",           "#00bc7d"),
    ("dark_chart3",           "#fe9a00"),
    ("dark_chart4",           "#ad46ff"),
    ("dark_chart5",           "#ff2056"),
]


def _row(type_name: str, hex_code: str) -> dict:
    return dict(
        id=sid(f"org/color/{type_name.replace('_', '-')}"),
        name=type_name.replace("_", " ").title(),
        description=f"--{type_name.replace('_', '-')}",
        hex_code=hex_code,
        type=type_name,
    )


colors = [_row(t, h) for t, h in _LIGHT] + [_row(t, h) for t, h in _DARK]
ALL_COLOR_IDS = [c["id"] for c in colors]
