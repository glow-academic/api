"""Standard resource seeds.

25 standards (5 levels per standard group): Excellent, Good, Acceptable, Marginal, Poor.
"""

from database.seeds.ids import sid

standards = [
    # ── Active Listening ──────────────────────────────────────────────────
    dict(
        id=sid("standard/active-listening/excellent"),
        name="Excellent",
        description="Consistently employs open-ended questions that empower students to discover solutions independently.",
        points=5,
        standard_group_id=sid("standard-group/active-listening"),
    ),
    dict(
        id=sid("standard/active-listening/good"),
        name="Good",
        description="Regularly uses guided questioning, encouraging student reasoning with occasional prompts.",
        points=4,
        standard_group_id=sid("standard-group/active-listening"),
    ),
    dict(
        id=sid("standard/active-listening/acceptable"),
        name="Acceptable",
        description="Occasionally guides students with questions but sometimes provides direct answers.",
        points=3,
        standard_group_id=sid("standard-group/active-listening"),
    ),
    dict(
        id=sid("standard/active-listening/marginal"),
        name="Marginal",
        description="Rarely uses questioning techniques, often resorting to hints or partial solutions.",
        points=2,
        standard_group_id=sid("standard-group/active-listening"),
    ),
    dict(
        id=sid("standard/active-listening/poor"),
        name="Poor",
        description="Directly provided the answer.",
        points=1,
        standard_group_id=sid("standard-group/active-listening"),
    ),
    # ── Time Management ───────────────────────────────────────────────────
    dict(
        id=sid("standard/time-management/excellent"),
        name="Excellent",
        description="Begins and concludes sessions within scheduled times, maximizing productivity and respecting student availability.",
        points=5,
        standard_group_id=sid("standard-group/time-management"),
    ),
    dict(
        id=sid("standard/time-management/good"),
        name="Good",
        description="Generally adheres to time allocations with minor deviations that do not impact session quality.",
        points=4,
        standard_group_id=sid("standard-group/time-management"),
    ),
    dict(
        id=sid("standard/time-management/acceptable"),
        name="Acceptable",
        description="Sometimes exceeds or finishes early, slightly affecting pacing yet maintaining core engagement.",
        points=3,
        standard_group_id=sid("standard-group/time-management"),
    ),
    dict(
        id=sid("standard/time-management/marginal"),
        name="Marginal",
        description="Frequently mismanages time, leading to rushed explanations or unnecessary prolongation.",
        points=2,
        standard_group_id=sid("standard-group/time-management"),
    ),
    dict(
        id=sid("standard/time-management/poor"),
        name="Poor",
        description="Ended the conversation really early, or made it last longer than needed.",
        points=1,
        standard_group_id=sid("standard-group/time-management"),
    ),
    # ── Adaptability ──────────────────────────────────────────────────────
    dict(
        id=sid("standard/adaptability/excellent"),
        name="Excellent",
        description="Perfectly adapts approach to diverse student emotional and attitude types.",
        points=5,
        standard_group_id=sid("standard-group/adaptability"),
    ),
    dict(
        id=sid("standard/adaptability/good"),
        name="Good",
        description="Mostly seamlessly adjusted communication and teaching style to effectively engage students across a wide range of emotions.",
        points=4,
        standard_group_id=sid("standard-group/adaptability"),
    ),
    dict(
        id=sid("standard/adaptability/acceptable"),
        name="Acceptable",
        description="Demonstrates thoughtful adjustments to support most student types, maintaining a supportive and responsive demeanor.",
        points=3,
        standard_group_id=sid("standard-group/adaptability"),
    ),
    dict(
        id=sid("standard/adaptability/marginal"),
        name="Marginal",
        description="Shows minimal ability to adjust to varied student behaviors, occasionally missing cues or responding inappropriately.",
        points=2,
        standard_group_id=sid("standard-group/adaptability"),
    ),
    dict(
        id=sid("standard/adaptability/poor"),
        name="Poor",
        description="Fails to adapt to different student types, responding uniformly without consideration of individual emotional or behavioral needs.",
        points=1,
        standard_group_id=sid("standard-group/adaptability"),
    ),
    # ── Communication ─────────────────────────────────────────────────────
    dict(
        id=sid("standard/communication/excellent"),
        name="Excellent",
        description="Consistently communicates with clarity and professionalism. Follows up when needed and maintains respectful boundaries in all interactions.",
        points=5,
        standard_group_id=sid("standard-group/communication"),
    ),
    dict(
        id=sid("standard/communication/good"),
        name="Good",
        description="Communicates respectfully and clearly with minor lapses in tone or timing. Upholds professional standards.",
        points=4,
        standard_group_id=sid("standard-group/communication"),
    ),
    dict(
        id=sid("standard/communication/acceptable"),
        name="Acceptable",
        description="Communication is mostly appropriate but may occasionally be abrupt, or overly casual.",
        points=3,
        standard_group_id=sid("standard-group/communication"),
    ),
    dict(
        id=sid("standard/communication/marginal"),
        name="Marginal",
        description="Shows limited awareness of tone or affect. May interrupt, dismiss student concerns, or respond in ways that feel cold or reactive.",
        points=2,
        standard_group_id=sid("standard-group/communication"),
    ),
    dict(
        id=sid("standard/communication/poor"),
        name="Poor",
        description="Demonstrates inappropriate or unprofessional behavior (e.g., sarcastic tone, dismissive responses, or failure to maintain respectful interaction).",
        points=1,
        standard_group_id=sid("standard-group/communication"),
    ),
    # ── Content Mastery ───────────────────────────────────────────────────
    dict(
        id=sid("standard/content-mastery/excellent"),
        name="Excellent",
        description="States core concepts clearly; explains in clear, bite-sized steps; uses analogies/visuals to clarify when needed; consistently checks understanding.",
        points=5,
        standard_group_id=sid("standard-group/content-mastery"),
    ),
    dict(
        id=sid("standard/content-mastery/good"),
        name="Good",
        description="Explains core concepts accurately and relates examples to key learning outcomes. Generally provides step-by-step reasoning and occasionally checks for student comprehension.",
        points=4,
        standard_group_id=sid("standard-group/content-mastery"),
    ),
    dict(
        id=sid("standard/content-mastery/acceptable"),
        name="Acceptable",
        description="Provides a basic overview of concepts but with occasional inaccuracies or lack of depth. Some explanations may feel rushed or cognitively dense.",
        points=3,
        standard_group_id=sid("standard-group/content-mastery"),
    ),
    dict(
        id=sid("standard/content-mastery/marginal"),
        name="Marginal",
        description="Demonstrates limited awareness of core concepts and offers explanations with minor errors. Explanations frequently rushed, dense, or skip logical steps; seldom checks comprehension.",
        points=2,
        standard_group_id=sid("standard-group/content-mastery"),
    ),
    dict(
        id=sid("standard/content-mastery/poor"),
        name="Poor",
        description="Misstates or omits concepts; dumps information or skips logic, confusing students; no comprehension checks and may rely on students for content.",
        points=1,
        standard_group_id=sid("standard-group/content-mastery"),
    ),
]
