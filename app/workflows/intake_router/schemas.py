from typing import Literal

from pydantic import BaseModel, Field


MissingInformationKey = Literal[
    "situation_summary",
    "document_type",
    "document_unclear_part",
    "document_upload",
    "digid_problem_description",
    "language_confirmation",
]

OpenLoopKey = Literal[
    "waiting_for_user_situation",
    "waiting_for_document_type",
    "waiting_for_document_unclear_part",
    "waiting_for_document_upload",
    "waiting_for_digid_problem_description",
]


class IntakeReasoningResult(BaseModel):
    situation_summary: str | None = None
    journey_candidate: str | None = None
    guided_journey_key: str | None = None
    missing_information: list[MissingInformationKey] = Field(default_factory=list)
    intake_complete: bool
    reply_text: str
    next_expected_input: Literal[
        "user_situation",
        "document_upload",
        "digid_problem_description",
        "document_processing",
    ] | None = None
    open_loop: OpenLoopKey | None = None
