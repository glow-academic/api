"""Standard group resource seeds.

5 standard groups shared across all base rubrics (Adaptability, Active Listening,
Content Mastery, Communication, Time Management).
"""

from uuid import UUID

standard_groups = [
    dict(
        id=UUID("019b3be4-3cc0-71ef-a1d4-b3d0deac7ead"),
        name="Adapts approach to individual student needs",
        short_name="Adaptability",
        description="Flexibility in teaching approach based on student personality and needs.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=UUID("019b3be4-3cc0-72ae-8181-dc2d5f6cee0d"),
        name="Facilitates student-driven learning",
        short_name="Active Listening",
        description="Ability to guide students to discover solutions independently through questioning.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=UUID("019b3be4-3cc0-72bb-aef9-c6d1c0a794d5"),
        name="Demonstrates understanding of core concepts",
        short_name="Content Mastery",
        description="Knowledge and articulation of core goals and learning outcomes.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=UUID("019b3be4-3cc0-72c6-8b83-ba801e217cbf"),
        name="Interpersonal communication and professionalism",
        short_name="Communication",
        description="Flexibility in teaching approach based on student personality and needs.",
        points=5,
        pass_points=4,
    ),
    dict(
        id=UUID("019b3be4-3cc0-72d3-9909-6eaf43e3d094"),
        name="Manages session time effectively",
        short_name="Time Management",
        description="Efficient use of session time and respect for scheduling.",
        points=5,
        pass_points=4,
    ),
]
