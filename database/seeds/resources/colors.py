"""Color resource seeds.

21 rows covering primary UI colors, background, surface, and chart colors.
Each color has a name, description, hex code, and type classification.
"""

from database.seeds.ids import sid

colors = [
    dict(
        id=sid("color/yellow"),
        name="Yellow",
        description="Yellow color",
        hex_code="#eab308",
        type="primary",
    ),
    dict(
        id=sid("color/green"),
        name="Green",
        description="Green color",
        hex_code="#22c55e",
        type="primary",
    ),
    dict(
        id=sid("color/red"),
        name="Red",
        description="Red color",
        hex_code="#ef4444",
        type="primary",
    ),
    dict(
        id=sid("color/cyan"),
        name="Cyan",
        description="Cyan color",
        hex_code="#06b6d4",
        type="primary",
    ),
    dict(
        id=sid("color/white-background"),
        name="White",
        description="White color",
        hex_code="#ffffff",
        type="background",
    ),
    dict(
        id=sid("color/white-surface"),
        name="White",
        description="White color",
        hex_code="#ffffff",
        type="surface",
    ),
    dict(
        id=sid("color/black"),
        name="Black",
        description="Black color",
        hex_code="#000000",
        type="chart1",
    ),
    dict(
        id=sid("color/gray"),
        name="Gray",
        description="Gray color",
        hex_code="#808080",
        type="chart3",
    ),
    dict(
        id=sid("color/violet"),
        name="Violet",
        description="Violet color",
        hex_code="#8b5cf6",
        type="primary",
    ),
    dict(
        id=sid("color/emerald"),
        name="Emerald",
        description="Emerald color",
        hex_code="#10b981",
        type="primary",
    ),
    dict(
        id=sid("color/blue"),
        name="Blue",
        description="Blue color",
        hex_code="#3b82f6",
        type="primary",
    ),
    dict(
        id=sid("color/lime"),
        name="Lime",
        description="Lime color",
        hex_code="#84cc16",
        type="primary",
    ),
    dict(
        id=sid("color/amber"),
        name="Amber",
        description="Amber color",
        hex_code="#f59e0b",
        type="primary",
    ),
    dict(
        id=sid("color/sky"),
        name="Sky",
        description="Sky color",
        hex_code="#0ea5e9",
        type="primary",
    ),
    dict(
        id=sid("color/teal"),
        name="Teal",
        description="Teal color",
        hex_code="#14b8a6",
        type="primary",
    ),
    dict(
        id=sid("color/indigo"),
        name="Indigo",
        description="Indigo color",
        hex_code="#6366f1",
        type="primary",
    ),
    dict(
        id=sid("color/purple"),
        name="Purple",
        description="Purple color",
        hex_code="#a855f7",
        type="primary",
    ),
    dict(
        id=sid("color/pink"),
        name="Pink",
        description="Pink color",
        hex_code="#ec4899",
        type="primary",
    ),
    dict(
        id=sid("color/fuchsia"),
        name="Fuchsia",
        description="Fuchsia color",
        hex_code="#d946ef",
        type="primary",
    ),
    dict(
        id=sid("color/rose"),
        name="Rose",
        description="Rose color",
        hex_code="#f43f5e",
        type="primary",
    ),
    dict(
        id=sid("color/orange"),
        name="Orange",
        description="Orange color",
        hex_code="#f97316",
        type="primary",
    ),
]
