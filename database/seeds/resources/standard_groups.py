"""Standard group resource seeds.

5 standard groups shared across all base rubrics (Adaptability, Active Listening,
Content Mastery, Communication, Time Management).
"""

from database.seeds.ids import sid

standard_groups = [
    dict(
        id=sid("standard-group/adaptability"),
        name="Adapts approach to individual student needs",
        short_name="Adaptability",
        description="Flexibility in teaching approach based on student personality and needs.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/active-listening"),
        name="Facilitates student-driven learning",
        short_name="Active Listening",
        description="Ability to guide students to discover solutions independently through questioning.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/content-mastery"),
        name="Demonstrates understanding of core concepts",
        short_name="Content Mastery",
        description="Knowledge and articulation of core goals and learning outcomes.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/communication"),
        name="Interpersonal communication and professionalism",
        short_name="Communication",
        description="Flexibility in teaching approach based on student personality and needs.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/time-management"),
        name="Manages session time effectively",
        short_name="Time Management",
        description="Efficient use of session time and respect for scheduling.",
        points=5,
        pass_points=4,
    ),
    # ── Persona-specific standard groups (for agent eval) ────────────────
    dict(
        id=sid("standard-group/persona-identity"),
        name="Creates a distinct, believable persona identity",
        short_name="Identity",
        description="Name and description capture a specific, differentiated character with clear personality traits.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/persona-behavioral-instructions"),
        name="Produces actionable behavioral instructions",
        short_name="Behavioral Instructions",
        description="Instructions are specific and actionable, driving consistent persona behavior including tone, boundaries, and response patterns.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/persona-parameter-alignment"),
        name="Selects appropriate parameter fields",
        short_name="Parameter Alignment",
        description="Selected parameter fields (temperament, intensity, role, type) accurately reflect the persona's intended character.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/persona-consistency"),
        name="Maintains coherence across all resources",
        short_name="Consistency",
        description="All resources are coherent — name matches description, description matches instructions, parameters match the overall persona identity.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=sid("standard-group/persona-completeness"),
        name="Populates all relevant persona resources",
        short_name="Completeness",
        description="All relevant resources are populated with meaningful values — nothing critical is left empty or at defaults when it should be specified.",
        points=5,
        pass_points=4,
    ),
]
