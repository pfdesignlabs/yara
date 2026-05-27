"""Cron-driven dispatcher that sends due reminders over WhatsApp."""

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.models import User
from app.services.message_service import create_outbound_message
from app.services.reminder_service import list_due_reminders, mark_reminder_sent

logger = logging.getLogger(__name__)

SOURCE_NODE = "reminder_dispatcher"


def dispatch_due_reminders(
    session: Session,
    twilio_client: TwilioWhatsAppClient | None = None,
) -> int:
    """Send every reminder whose `scheduled_for` is in the past.

    Returns the number of reminders successfully sent. Per-reminder errors
    (Twilio failure, missing user, ...) are logged but do not crash the
    tick — the next interval will retry rows that are still `scheduled`.
    """
    twilio_client = twilio_client or TwilioWhatsAppClient()
    due = list_due_reminders(session)
    sent_count = 0

    for reminder in due:
        if reminder.conversation_id is None:
            logger.warning(
                "reminder %s has no conversation_id; skipping (stand-alone "
                "reminders are not supported yet)",
                reminder.id,
            )
            continue

        try:
            user = session.get(User, reminder.user_id)
            if user is None:
                logger.error(
                    "reminder %s references missing user %s; skipping",
                    reminder.id,
                    reminder.user_id,
                )
                continue

            body = reminder.body_template
            whatsapp_message_id = twilio_client.send_whatsapp_message(
                to_phone_number=user.phone_number, body=body
            )

            create_outbound_message(
                session,
                user_id=reminder.user_id,
                conversation_id=reminder.conversation_id,
                content_text=body,
                whatsapp_message_id=whatsapp_message_id,
                source_node=SOURCE_NODE,
            )
            mark_reminder_sent(
                session, reminder_id=reminder.id, sent_message_id=whatsapp_message_id
            )
            sent_count += 1
            logger.info("reminder %s sent (twilio sid=%s)", reminder.id, whatsapp_message_id)
        except Exception:
            logger.exception("failed to dispatch reminder %s", reminder.id)

    return sent_count


def dispatch_due_reminders_job() -> None:
    """APScheduler entry-point — opens its own session."""
    session = SessionLocal()
    try:
        dispatch_due_reminders(session)
    finally:
        session.close()
