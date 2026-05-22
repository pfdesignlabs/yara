from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.schemas.whatsapp import InboundWhatsAppMessage


def create_inbound_message(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    inbound_message: InboundWhatsAppMessage,
    media_storage_path: str | None = None,
) -> Message:
    message = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        direction="inbound",
        message_type=inbound_message.message_type,
        content_text=inbound_message.text,
        media_storage_path=media_storage_path,
        media_mime_type=inbound_message.media_content_type,
        whatsapp_message_id=inbound_message.external_message_id,
        raw_payload_json=inbound_message.raw_payload,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def create_outbound_message(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    content_text: str,
    whatsapp_message_id: str | None = None,
    raw_payload_json: dict | None = None,
    source_node: str | None = None,
) -> Message:
    message = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        direction="outbound",
        message_type="text",
        content_text=content_text,
        whatsapp_message_id=whatsapp_message_id,
        raw_payload_json=raw_payload_json,
        source_node=source_node,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def get_recent_messages_for_conversation(
    session: Session,
    *,
    conversation_id: str,
    limit: int = 5,
) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = session.scalars(statement).all()
    return list(reversed(messages))
