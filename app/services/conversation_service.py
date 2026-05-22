from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def get_active_conversation_for_user(session: Session, user_id: str) -> Conversation | None:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
    )
    return session.scalars(statement).first()


def get_or_create_active_conversation(session: Session, user_id: str) -> Conversation:
    conversation = get_active_conversation_for_user(session, user_id)
    if conversation is not None:
        return conversation

    conversation = Conversation(user_id=user_id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def touch_conversation(session: Session, conversation: Conversation) -> Conversation:
    now = datetime.utcnow()
    conversation.last_message_at = now
    conversation.updated_at = now
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation
