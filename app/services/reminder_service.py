"""CRUD for the polymorphic `reminders` table.

Used by tool wrappers (LLM-facing) and by the cron dispatcher (Phase 4).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.reminder import Reminder

REMINDER_REPLY_WINDOW = timedelta(hours=48)
_REMINDER_SOURCE_NODE = "reminder_dispatcher"

_ALLOWED_STATUSES = {"scheduled", "sent", "cancelled"}


def create_reminder(
    session: Session,
    *,
    user_id: str,
    conversation_id: str | None,
    target_type: str,
    target_id: str | None,
    scheduled_for: datetime,
    body_template: str,
) -> Reminder:
    reminder = Reminder(
        user_id=user_id,
        conversation_id=conversation_id,
        target_type=target_type,
        target_id=target_id,
        scheduled_for=scheduled_for,
        body_template=body_template,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def list_due_reminders(session: Session) -> list[Reminder]:
    statement = (
        select(Reminder)
        .where(Reminder.status == "scheduled", Reminder.scheduled_for <= datetime.utcnow())
        .order_by(Reminder.scheduled_for.asc())
    )
    return list(session.scalars(statement))


def mark_reminder_sent(session: Session, *, reminder_id: str, sent_message_id: str) -> Reminder:
    reminder = session.get(Reminder, reminder_id)
    if reminder is None:
        raise ValueError(f"reminder {reminder_id!r} not found")
    reminder.status = "sent"
    reminder.sent_at = datetime.utcnow()
    reminder.sent_message_id = sent_message_id
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def find_reminder_user_is_replying_to(session: Session, *, conversation_id: str) -> Reminder | None:
    """Return the Reminder the user's latest inbound message is responding to.

    Detection: look at the most-recent outbound message in this conversation
    that precedes the most-recent inbound. If that outbound was sent by the
    reminder dispatcher within the last 48 hours, the user is replying to its
    Reminder. Any other interleaving message (a doc_helper reply, an older
    inbound) means the user has moved on — return None.
    """
    latest_inbound = session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.direction == "inbound")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if latest_inbound is None:
        return None

    previous_outbound = session.scalar(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == "outbound",
            Message.created_at < latest_inbound.created_at,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if previous_outbound is None or previous_outbound.source_node != _REMINDER_SOURCE_NODE:
        return None

    age = datetime.now(UTC) - previous_outbound.created_at
    if age > REMINDER_REPLY_WINDOW:
        return None

    return session.scalar(
        select(Reminder).where(Reminder.sent_message_id == previous_outbound.whatsapp_message_id)
    )


def cancel_reminder(session: Session, *, reminder_id: str) -> Reminder:
    reminder = session.get(Reminder, reminder_id)
    if reminder is None:
        raise ValueError(f"reminder {reminder_id!r} not found")
    reminder.status = "cancelled"
    reminder.cancelled_at = datetime.utcnow()
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder
