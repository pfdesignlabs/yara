"""LLM-facing tool wrappers around the action_service CRUD."""

from datetime import datetime
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool
from sqlalchemy.orm import Session

from app.services.action_service import (
    create_action as _create_action_service,
)
from app.services.action_service import (
    mark_action_status,
)


@tool
def mark_action_done(
    action_id: str,
    session: Annotated[Session, InjectedToolArg],
) -> str:
    """Mark an action as completed.

    Use this when the user confirms they did the suggested step (or
    explicitly skipped it and considers it done). Sets the action's
    `status` to `'done'` and stamps `completed_at`.
    """
    action = mark_action_status(session, action_id=action_id, status="done")
    return f"Action {action.id} marked as done."


@tool
def create_action(
    description: str,
    source_type: str,
    session: Annotated[Session, InjectedToolArg],
    user_id: Annotated[str, InjectedToolArg],
    conversation_id: Annotated[str | None, InjectedToolArg],
    source_id: str | None = None,
    action_type: str | None = None,
    urgency: str | None = None,
    deadline_date: str | None = None,
) -> str:
    """Create a new action for the user.

    Use this when the user mentions a concrete next step they want to
    track (e.g. "remind me to file my bezwaar", "I should call IND
    tomorrow"). Use it also for follow-up tasks that emerge mid-conversation
    on top of the original document's actions.

    Args:
        description: short human-readable description of the action.
        source_type: where the action originated (e.g. "document_helper",
            "conversation", "manual").
        source_id: optional UUID linking the action to a specific source
            entity (e.g. a document_id).
        action_type: optional short category (e.g. "bezwaar", "afspraak_maken").
        urgency: one of "today", "this_week", "this_month", "no_deadline".
        deadline_date: optional ISO 8601 string (e.g. "2026-06-15" or
            "2026-06-15T14:00:00Z").
    """
    deadline = _parse_iso(deadline_date) if deadline_date else None
    action = _create_action_service(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
        source_type=source_type,
        source_id=source_id,
        action_type=action_type,
        description=description,
        urgency=urgency,
        deadline_date=deadline,
    )
    return f"Action {action.id} created (status=pending)."


def _parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 datetime string into a datetime object."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
