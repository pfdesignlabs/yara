"""CRUD for the polymorphic `reminders` table.

Used by tool wrappers (LLM-facing) and by the cron dispatcher (Phase 4).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reminder import Reminder

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
