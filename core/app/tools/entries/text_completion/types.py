"""Entry types — handcrafted, co-located with handler."""

from uuid import UUID

from pydantic import BaseModel


class CreateTextCompletionResponse(BaseModel):
    id: UUID
