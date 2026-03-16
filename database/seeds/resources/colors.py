"""Color resource seeds.

21 rows covering primary UI colors, background, surface, and chart colors.
Each color has a name, description, hex code, and type classification.
"""

from uuid import UUID

colors = [
    dict(
        id=UUID("019b995b-52f6-7759-98be-647af770b92b"),
        name="Yellow",
        description="Yellow color",
        hex_code="#eab308",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52f6-773e-9996-4bb11ef1e435"),
        name="Green",
        description="Green color",
        hex_code="#22c55e",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52f6-7749-8ebd-e1c6bb66de89"),
        name="Red",
        description="Red color",
        hex_code="#ef4444",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52f6-774f-be3e-db1b84a0c1f0"),
        name="Cyan",
        description="Cyan color",
        hex_code="#06b6d4",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52ef-7e27-97ea-01f0e94aa14c"),
        name="White",
        description="White color",
        hex_code="#ffffff",
        type="background",
    ),
    dict(
        id=UUID("019b995b-52f0-71ba-885b-7d544fefed50"),
        name="White",
        description="White color",
        hex_code="#ffffff",
        type="surface",
    ),
    dict(
        id=UUID("019b995b-52f1-76ba-8ec2-efb00cde1b0b"),
        name="Black",
        description="Black color",
        hex_code="#000000",
        type="chart1",
    ),
    dict(
        id=UUID("019b995b-52f1-7d09-889a-b24887bd2cb2"),
        name="Gray",
        description="Gray color",
        hex_code="#808080",
        type="chart3",
    ),
    dict(
        id=UUID("019b995b-52f6-7750-8e0d-a4a37ff9ad13"),
        name="Violet",
        description="Violet color",
        hex_code="#8b5cf6",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52f6-7754-9d33-d3e56f2063e0"),
        name="Emerald",
        description="Emerald color",
        hex_code="#10b981",
        type="primary",
    ),
    dict(
        id=UUID("019b995b-52f6-7746-a592-fbc338f61f5f"),
        name="Blue",
        description="Blue color",
        hex_code="#3b82f6",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7e98-a24c-3b7b5b405595"),
        name="Lime",
        description="Lime color",
        hex_code="#84cc16",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7e82-99e7-a4bdcf523add"),
        name="Amber",
        description="Amber color",
        hex_code="#f59e0b",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7eba-b774-31acf1776121"),
        name="Sky",
        description="Sky color",
        hex_code="#0ea5e9",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7eac-aa8a-511cdd4a62ff"),
        name="Teal",
        description="Teal color",
        hex_code="#14b8a6",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7eca-b531-82f53a6bee32"),
        name="Indigo",
        description="Indigo color",
        hex_code="#6366f1",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7efb-81d8-6497789c4548"),
        name="Purple",
        description="Purple color",
        hex_code="#a855f7",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7f12-a888-814580aeed8b"),
        name="Pink",
        description="Pink color",
        hex_code="#ec4899",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7f09-b298-ed08d8aaaa02"),
        name="Fuchsia",
        description="Fuchsia color",
        hex_code="#d946ef",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7f1f-860c-fe53858b71f8"),
        name="Rose",
        description="Rose color",
        hex_code="#f43f5e",
        type="primary",
    ),
    dict(
        id=UUID("019b9eb0-c7ab-7dce-a088-16018f3dbf37"),
        name="Orange",
        description="Orange color",
        hex_code="#f97316",
        type="primary",
    ),
]
