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
]
