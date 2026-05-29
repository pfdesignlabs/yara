import logging

import httpx
from twilio.rest import Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TYPING_INDICATOR_URL = "https://messaging.twilio.com/v2/Indicators/Typing.json"

# Twilio enforces ~1600 chars per outbound WhatsApp message body. Pick a
# slightly lower split threshold so we never hit the wall on edge cases
# (multi-byte chars, percent-encoded mailto URLs, etc.).
_MAX_WHATSAPP_LEN = 1500


def _split_for_whatsapp(body: str) -> list[str]:
    """Chunk `body` into pieces of at most `_MAX_WHATSAPP_LEN` characters.

    Prefers to break on a blank line, then a single newline, then a space —
    only falling back to a hard split when none of those exist within the
    first chunk. A `mailto:` URL has no newlines, so a long mailto-link
    naturally becomes its own chunk after the explanation text.
    """
    if len(body) <= _MAX_WHATSAPP_LEN:
        return [body]

    chunks: list[str] = []
    remaining = body
    while len(remaining) > _MAX_WHATSAPP_LEN:
        window = remaining[:_MAX_WHATSAPP_LEN]
        for boundary in ("\n\n", "\n", " "):
            split = window.rfind(boundary)
            if split > _MAX_WHATSAPP_LEN // 3:
                break
        else:
            split = _MAX_WHATSAPP_LEN
        chunks.append(remaining[:split].rstrip())
        remaining = remaining[split:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


class TwilioWhatsAppClient:
    def __init__(self) -> None:
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.from_number = settings.twilio_whatsapp_number

    def send_whatsapp_message(self, to_phone_number: str, body: str) -> str:
        """Send `body` as one or more WhatsApp messages and return the last SID.

        Bodies longer than ~1500 characters are split into multiple Twilio
        sends so we never hit the 1600-char limit (encountered when a mailto
        URL with a bilingual body is appended to the assistant reply).
        """
        chunks = _split_for_whatsapp(body)
        if len(chunks) > 1:
            logger.info(
                "splitting outbound whatsapp into %d chunks (total %d chars)",
                len(chunks),
                len(body),
            )
        last_sid = ""
        for chunk in chunks:
            message = self.client.messages.create(
                from_=self.from_number,
                to=f"whatsapp:{to_phone_number}",
                body=chunk,
            )
            last_sid = message.sid
        return last_sid

    def send_typing_indicator(self, inbound_message_sid: str) -> None:
        """Show the 'typing…' bubble in WhatsApp while we prepare a reply.

        The indicator auto-clears after 25s or when our actual reply is
        delivered, whichever comes first. Twilio also marks the referenced
        inbound message as read. Failures are logged but never raised — this
        is a best-effort UX hint, not a hard dependency of the reply path.
        """
        try:
            response = httpx.post(
                _TYPING_INDICATOR_URL,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={"messageId": inbound_message_sid, "channel": "whatsapp"},
                timeout=5.0,
            )
            response.raise_for_status()
        except Exception:
            logger.exception("typing indicator failed for inbound message %s", inbound_message_sid)
