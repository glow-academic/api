"""Generation dispatch utilities for mapping agent roles to generation handlers."""


def get_generation_handler(agent_role: str) -> str:
    """
    Determine the generation handler type based on agent role.

    Args:
        agent_role: The agent role string (e.g., "scenario", "image", "video", "voice")

    Returns:
        The generation handler type: "text", "image", "video", or "audio"

    Raises:
        ValueError: If the agent_role is not recognized
    """
    # Text generation handlers
    text_roles = {
        "scenario",
        "document",
        "simulation",
        "grade",
        "hint",
        "classify",
        "member",
        "prompt",
        "rubric",
        "title",
        "audio",
    }

    # Image generation handlers
    image_roles = {"image"}

    # Video generation handlers
    video_roles = {"video"}

    # Audio generation handlers (ephemeral sessions only)
    audio_roles = {"voice"}

    if agent_role in text_roles:
        return "text"
    elif agent_role in image_roles:
        return "image"
    elif agent_role in video_roles:
        return "video"
    elif agent_role in audio_roles:
        return "audio"
    else:
        raise ValueError(f"Unknown agent role: {agent_role}")
