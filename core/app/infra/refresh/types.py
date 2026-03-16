"""Shared Pydantic models for composable refresh responses."""

from pydantic import BaseModel


class RefreshResponse(BaseModel):
    """Standard response for composable refresh endpoints.

    Returned by all `refresh_{artifact}_client` infra functions.
    """

    success: bool
    refreshed_views: list[str]
    invalidated_tags: list[str]
