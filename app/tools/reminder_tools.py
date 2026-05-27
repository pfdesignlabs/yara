"""LLM-facing tool wrappers around the reminder_service CRUD."""

from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool
from sqlalchemy.orm import Session

from app.services.reminder_service import (
    create_reminder as _create_reminder_service,
)
from app.tools._helpers import parse_iso


@tool
def create_reminder(
    target_type: str,
    when_iso: str,
    body_template: str,
    session: Annotated[Session, InjectedToolArg],
    user_id: Annotated[str, InjectedToolArg],
    conversation_id: Annotated[str | None, InjectedToolArg],
    target_id: str | None = None,
) -> str:
    """Schedule a proactive reminder.

    Use this when the user agrees to be reminded about a pending action
    (e.g. "yes, please remind me tomorrow if I haven't filed the bezwaar
    yet") or asks for a stand-alone follow-up.

    Args:
        target_type: what this reminder is about — typically "action"
            (paired with target_id=<action.id>) or "conversation" (for
            a stand-alone follow-up on the conversation as a whole).
        when_iso: ISO 8601 datetime string for when the reminder should
            fire (e.g. "2026-06-15T09:00:00Z" or "2026-06-15").
        body_template: the message that will be sent to the user when
            the reminder fires. Can include placeholders like
            `{{action_type}}` that the dispatcher renders.
        target_id: optional UUID of the target entity (an action ID
            when target_type="action"). Leave null for conversation-
            level reminders.
    """
    scheduled_for = parse_iso(when_iso)
    reminder = _create_reminder_service(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
        target_type=target_type,
        target_id=target_id,
        scheduled_for=scheduled_for,
        body_template=body_template,
    )
    return f"Reminder {reminder.id} scheduled for {scheduled_for.isoformat()}."
