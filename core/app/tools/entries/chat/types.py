"""Chat entry types — handcrafted, co-located with handler."""

from uuid import UUID

from pydantic import BaseModel


class CreateChatResponse(BaseModel):
    id: UUID


class GetChatResponse(BaseModel):
    id: UUID
    parent_id: UUID | None
    scenario_id: UUID | None
    department_ids: list[UUID]
    document_ids: list[UUID]
    parameter_field_ids: list[UUID]
    question_ids: list[UUID]
    option_ids: list[UUID]
    video_ids: list[UUID]
    image_ids: list[UUID]
    problem_statement_ids: list[UUID]
    objective_ids: list[UUID]
    flag_ids: list[UUID]
    name_ids: list[UUID]
    description_ids: list[UUID]
    persona_ids: list[UUID]
    rubric_ids: list[UUID]
    standard_ids: list[UUID]
    standard_group_ids: list[UUID]
    video_enabled: bool | None
    problem_statement_enabled: bool | None
    objectives_enabled: bool | None
    images_enabled: bool | None
    questions_enabled: bool | None
    position: int | None
    time_limit: int | None
    negative_time: bool | None
