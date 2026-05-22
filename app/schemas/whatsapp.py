from typing import Any, Literal

from pydantic import BaseModel, Field


class InboundWhatsAppMessage(BaseModel):
    provider: Literal["twilio"] = "twilio"
    channel: Literal["whatsapp"] = "whatsapp"
    external_message_id: str | None = None
    phone_number: str
    profile_name: str | None = None
    message_type: Literal["text", "image", "document", "unknown"] = "unknown"
    text: str | None = None
    media_url: str | None = None
    media_content_type: str | None = None
    num_media: int = 0
    raw_payload: dict[str, Any] = Field(default_factory=dict)
