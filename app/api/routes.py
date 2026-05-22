from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.integrations.twilio_whatsapp import normalize_twilio_webhook
from app.services.conversation_service import get_or_create_active_conversation, touch_conversation
from app.services.message_service import create_inbound_message, create_outbound_message
from app.services.user_service import get_or_create_user_by_phone_number
from app.workflows.router import run_router

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp_webhook(
    request: Request, session: Session = Depends(get_db_session)
) -> dict:
    form = await request.form()
    normalized = normalize_twilio_webhook(form)

    user = get_or_create_user_by_phone_number(
        session,
        phone_number=normalized.phone_number,
        display_name=normalized.profile_name,
    )
    conversation = get_or_create_active_conversation(session, user.id)
    message = create_inbound_message(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        inbound_message=normalized,
    )
    touch_conversation(session, conversation)

    reply_text, source_node = run_router(
        session,
        conversation_id=conversation.id,
        user_id=user.id,
    )

    outbound_sid = TwilioWhatsAppClient().send_whatsapp_message(
        to_phone_number=normalized.phone_number,
        body=reply_text,
    )
    create_outbound_message(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        content_text=reply_text,
        whatsapp_message_id=outbound_sid,
        source_node=source_node,
    )

    return {
        "status": "ok",
        "user_id": user.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
    }
