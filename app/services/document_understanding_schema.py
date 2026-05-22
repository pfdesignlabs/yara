from pydantic import BaseModel


class DocumentUnderstandingResult(BaseModel):
    document_type: str | None = None
    journey_candidate: str | None = None
    summary: str
    suggested_next_step: str | None = None
