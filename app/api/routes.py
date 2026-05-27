import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.integrations.twilio_whatsapp import normalize_twilio_webhook
from app.services.attachment_service import create_document, download_twilio_media
from app.services.conversation_service import get_or_create_active_conversation, touch_conversation
from app.services.message_service import create_inbound_message, create_outbound_message
from app.services.user_service import get_or_create_user_by_phone_number
from app.workflows.router import run_router

logger = logging.getLogger(__name__)

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

    media_storage_path = None
    if normalized.media_url and normalized.media_content_type:
        try:
            file_path = download_twilio_media(
                media_url=normalized.media_url,
                mime_type=normalized.media_content_type,
                user_id=user.id,
                external_message_id=normalized.external_message_id or "unknown",
            )
            media_storage_path = str(file_path)
        except Exception:
            logger.exception(
                "Failed to download Twilio media for user_id=%s, message_sid=%s",
                user.id,
                normalized.external_message_id,
            )

    message = create_inbound_message(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        inbound_message=normalized,
        media_storage_path=media_storage_path,
    )

    if media_storage_path and normalized.media_content_type:
        create_document(
            session,
            user_id=user.id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            file_storage_path=Path(media_storage_path),
            mime_type=normalized.media_content_type,
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
