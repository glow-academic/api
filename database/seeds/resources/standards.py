"""Standard resource seeds.

25 standards (5 levels per standard group): Excellent, Good, Acceptable, Marginal, Poor.
"""

from uuid import UUID

standards = [
    # ── Active Listening ──────────────────────────────────────────────────
    dict(
        id=UUID("019b3be4-3ccb-708d-80e7-51b691b555a7"),
        name="Excellent",
        description="Consistently employs open-ended questions that empower students to discover solutions independently.",
        points=5,
        standard_group_id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-79f6-94ba-79f5d64f4da5"),
        name="Good",
        description="Regularly uses guided questioning, encouraging student reasoning with occasional prompts.",
        points=4,
        standard_group_id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7a0a-aa26-89b6b78b15c8"),
        name="Acceptable",
        description="Occasionally guides students with questions but sometimes provides direct answers.",
        points=3,
        standard_group_id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7a13-b68a-7356120e342d"),
        name="Marginal",
        description="Rarely uses questioning techniques, often resorting to hints or partial solutions.",
        points=2,
        standard_group_id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7c83-bf5d-78130778498f"),
        name="Poor",
        description="Directly provided the answer.",
        points=1,
        standard_group_id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
    ),
    # ── Time Management ───────────────────────────────────────────────────
    dict(
        id=UUID("019b3be4-3ccb-7c8d-9223-a4036e26ca5c"),
        name="Excellent",
        description="Begins and concludes sessions within scheduled times, maximizing productivity and respecting student availability.",
        points=5,
        standard_group_id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7c9a-a648-3653254dd832"),
        name="Good",
        description="Generally adheres to time allocations with minor deviations that do not impact session quality.",
        points=4,
        standard_group_id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7ca6-9eae-11efeb2889ef"),
        name="Acceptable",
        description="Sometimes exceeds or finishes early, slightly affecting pacing yet maintaining core engagement.",
        points=3,
        standard_group_id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7cb6-9c52-3c1a6049430f"),
        name="Marginal",
        description="Frequently mismanages time, leading to rushed explanations or unnecessary prolongation.",
        points=2,
        standard_group_id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7cc1-ac03-582413caba8c"),
        name="Poor",
        description="Ended the conversation really early, or made it last longer than needed.",
        points=1,
        standard_group_id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
    ),
    # ── Adaptability ──────────────────────────────────────────────────────
    dict(
        id=UUID("019b3be4-3ccb-7ccd-b136-489245b9d44e"),
        name="Excellent",
        description="Perfectly adapts approach to diverse student emotional and attitude types.",
        points=5,
        standard_group_id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7cdd-8d41-28b981adbb2b"),
        name="Good",
        description="Mostly seamlessly adjusted communication and teaching style to effectively engage students across a wide range of emotions.",
        points=4,
        standard_group_id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7ceb-86fc-0faa43b38349"),
        name="Acceptable",
        description="Demonstrates thoughtful adjustments to support most student types, maintaining a supportive and responsive demeanor.",
        points=3,
        standard_group_id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7cf4-bdf1-adc4bbac9025"),
        name="Marginal",
        description="Shows minimal ability to adjust to varied student behaviors, occasionally missing cues or responding inappropriately.",
        points=2,
        standard_group_id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7cfe-91dc-4c083ceb6478"),
        name="Poor",
        description="Fails to adapt to different student types, responding uniformly without consideration of individual emotional or behavioral needs.",
        points=1,
        standard_group_id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
    ),
    # ── Communication ─────────────────────────────────────────────────────
    dict(
        id=UUID("019b3be4-3ccb-7d07-bc1f-8bbc88df7d59"),
        name="Excellent",
        description="Consistently communicates with clarity and professionalism. Follows up when needed and maintains respectful boundaries in all interactions.",
        points=5,
        standard_group_id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7d11-b870-8930594fec0d"),
        name="Good",
        description="Communicates respectfully and clearly with minor lapses in tone or timing. Upholds professional standards.",
        points=4,
        standard_group_id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7d18-a14f-f68e642a3cfd"),
        name="Acceptable",
        description="Communication is mostly appropriate but may occasionally be abrupt, or overly casual.",
        points=3,
        standard_group_id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7d21-9879-c7f0a428f46d"),
        name="Marginal",
        description="Shows limited awareness of tone or affect. May interrupt, dismiss student concerns, or respond in ways that feel cold or reactive.",
        points=2,
        standard_group_id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7d2b-a60d-6347af838659"),
        name="Poor",
        description="Demonstrates inappropriate or unprofessional behavior (e.g., sarcastic tone, dismissive responses, or failure to maintain respectful interaction).",
        points=1,
        standard_group_id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
    ),
    # ── Content Mastery ───────────────────────────────────────────────────
    dict(
        id=UUID("019b3be4-3ccb-7d32-ab5d-00b1134aa994"),
        name="Excellent",
        description="States core concepts clearly; explains in clear, bite-sized steps; uses analogies/visuals to clarify when needed; consistently checks understanding.",
        points=5,
        standard_group_id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    ),
    dict(
        id=UUID("019b3be4-3ccb-7d3b-97df-8c24df676cf2"),
        name="Good",
        description="Explains core concepts accurately and relates examples to key learning outcomes. Generally provides step-by-step reasoning and occasionally checks for student comprehension.",
        points=4,
        standard_group_id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    ),
    dict(
        id=UUID("019b3be4-3ccc-73e6-9e54-e88b8c142cb2"),
        name="Acceptable",
        description="Provides a basic overview of concepts but with occasional inaccuracies or lack of depth. Some explanations may feel rushed or cognitively dense.",
        points=3,
        standard_group_id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    ),
    dict(
        id=UUID("019b3be4-3ccc-73f7-965d-791773e2baba"),
        name="Marginal",
        description="Demonstrates limited awareness of core concepts and offers explanations with minor errors. Explanations frequently rushed, dense, or skip logical steps; seldom checks comprehension.",
        points=2,
        standard_group_id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    ),
    dict(
        id=UUID("019b3be4-3ccc-7402-a396-24de5a95f832"),
        name="Poor",
        description="Misstates or omits concepts; dumps information or skips logic, confusing students; no comprehension checks and may rely on students for content.",
        points=1,
        standard_group_id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
    ),
]
