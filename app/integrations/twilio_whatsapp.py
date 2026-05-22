from collections.abc import Mapping

from app.schemas.whatsapp import InboundWhatsAppMessage

TEXT_MEDIA_PREFIXES = {
    "image/": "image",
    "application/pdf": "document",
}


def _normalize_phone_number(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("whatsapp:", "").strip()


def _detect_message_type(num_media: int, media_content_type: str | None, text: str | None) -> str:
    if num_media > 0:
        if media_content_type:
            if media_content_type.startswith("image/"):
                return "image"
            if media_content_type == "application/pdf":
                return "document"
        return "unknown"
    if text:
        return "text"
    return "unknown"


def normalize_twilio_webhook(form_data: Mapping[str, str]) -> InboundWhatsAppMessage:
    num_media = int(form_data.get("NumMedia", "0") or 0)
    text = form_data.get("Body") or None
    media_url = form_data.get("MediaUrl0") or None
    media_content_type = form_data.get("MediaContentType0") or None

    return InboundWhatsAppMessage(
        external_message_id=form_data.get("MessageSid"),
        phone_number=_normalize_phone_number(form_data.get("From")),
        profile_name=form_data.get("ProfileName"),
        message_type=_detect_message_type(num_media, media_content_type, text),
        text=text,
        media_url=media_url,
        media_content_type=media_content_type,
        num_media=num_media,
        raw_payload=dict(form_data),
    )
