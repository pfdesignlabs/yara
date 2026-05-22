from pydantic import BaseModel


class GuidedJourneyFactExtractionResult(BaseModel):
    values: dict[str, bool | str | None]
