"""Color resource seeds.

Palette roles covered: primary, secondary, accent, background, surface,
foreground, muted, success, warning, danger, info, and chart1-5. Each role
has multiple options so theme pickers have real choices per slot.
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
    # ----- Secondary -----
    dict(id=sid("color/secondary-slate"),  name="Slate",   description="Slate secondary",   hex_code="#64748b", type="secondary"),
    dict(id=sid("color/secondary-zinc"),   name="Zinc",    description="Zinc secondary",    hex_code="#71717a", type="secondary"),
    dict(id=sid("color/secondary-stone"),  name="Stone",   description="Stone secondary",   hex_code="#78716c", type="secondary"),
    dict(id=sid("color/secondary-neutral"),name="Neutral", description="Neutral secondary", hex_code="#737373", type="secondary"),

    # ----- Accent -----
    dict(id=sid("color/accent-violet"),  name="Violet",  description="Violet accent",  hex_code="#a78bfa", type="accent"),
    dict(id=sid("color/accent-teal"),    name="Teal",    description="Teal accent",    hex_code="#2dd4bf", type="accent"),
    dict(id=sid("color/accent-pink"),    name="Pink",    description="Pink accent",    hex_code="#f472b6", type="accent"),
    dict(id=sid("color/accent-amber"),   name="Amber",   description="Amber accent",   hex_code="#fbbf24", type="accent"),

    # ----- Background -----
    dict(id=sid("color/background-slate-50"),  name="Slate 50",  description="Slate 50 background",  hex_code="#f8fafc", type="background"),
    dict(id=sid("color/background-zinc-50"),   name="Zinc 50",   description="Zinc 50 background",   hex_code="#fafafa", type="background"),
    dict(id=sid("color/background-neutral-50"),name="Neutral 50",description="Neutral 50 background",hex_code="#fafafa", type="background"),
    dict(id=sid("color/background-dark"),      name="Dark",      description="Dark background",      hex_code="#0f172a", type="background"),

    # ----- Foreground -----
    dict(id=sid("color/foreground-slate-900"), name="Slate 900", description="Slate 900 foreground", hex_code="#0f172a", type="foreground"),
    dict(id=sid("color/foreground-black"),     name="Black",     description="Black foreground",     hex_code="#000000", type="foreground"),
    dict(id=sid("color/foreground-neutral-50"),name="Neutral 50",description="Neutral 50 foreground",hex_code="#fafafa", type="foreground"),

    # ----- Muted -----
    dict(id=sid("color/muted-slate-100"),   name="Slate 100",   description="Slate 100 muted",   hex_code="#f1f5f9", type="muted"),
    dict(id=sid("color/muted-zinc-100"),    name="Zinc 100",    description="Zinc 100 muted",    hex_code="#f4f4f5", type="muted"),
    dict(id=sid("color/muted-neutral-100"), name="Neutral 100", description="Neutral 100 muted", hex_code="#f5f5f5", type="muted"),

    # ----- Success -----
    dict(id=sid("color/success-green"),   name="Green",   description="Green success",   hex_code="#22c55e", type="success"),
    dict(id=sid("color/success-emerald"), name="Emerald", description="Emerald success", hex_code="#10b981", type="success"),
    dict(id=sid("color/success-lime"),    name="Lime",    description="Lime success",    hex_code="#84cc16", type="success"),

    # ----- Warning -----
    dict(id=sid("color/warning-amber"),   name="Amber",  description="Amber warning",  hex_code="#f59e0b", type="warning"),
    dict(id=sid("color/warning-yellow"),  name="Yellow", description="Yellow warning", hex_code="#eab308", type="warning"),
    dict(id=sid("color/warning-orange"),  name="Orange", description="Orange warning", hex_code="#f97316", type="warning"),

    # ----- Danger -----
    dict(id=sid("color/danger-red"),   name="Red",   description="Red danger",   hex_code="#ef4444", type="danger"),
    dict(id=sid("color/danger-rose"),  name="Rose",  description="Rose danger",  hex_code="#f43f5e", type="danger"),
    dict(id=sid("color/danger-crimson"),name="Crimson",description="Crimson danger",hex_code="#dc2626", type="danger"),

    # ----- Info -----
    dict(id=sid("color/info-blue"),  name="Blue",  description="Blue info",  hex_code="#3b82f6", type="info"),
    dict(id=sid("color/info-sky"),   name="Sky",   description="Sky info",   hex_code="#0ea5e9", type="info"),
    dict(id=sid("color/info-cyan"),  name="Cyan",  description="Cyan info",  hex_code="#06b6d4", type="info"),
    dict(id=sid("color/info-indigo"),name="Indigo",description="Indigo info",hex_code="#6366f1", type="info"),
]
