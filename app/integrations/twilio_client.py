from twilio.rest import Client

from app.core.config import get_settings

settings = get_settings()


class TwilioWhatsAppClient:
    def __init__(self) -> None:
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.from_number = settings.twilio_whatsapp_number

    def send_whatsapp_message(self, to_phone_number: str, body: str) -> str:
        message = self.client.messages.create(
            from_=self.from_number,
            to=f"whatsapp:{to_phone_number}",
            body=body,
        )
        return message.sid
