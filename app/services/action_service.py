"""CRUD for the polymorphic `actions` table.

No LLM / tool coupling — pure data layer. Specialist nodes (doc_helper,
intake, future ones) call these via tool wrappers in `app/tools/`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action import Action

_ALLOWED_STATUSES = {"pending", "in_progress", "done", "skipped"}


def create_action(
    session: Session,
    *,
    user_id: str,
    conversation_id: str | None,
    source_type: str,
    source_id: str | None,
    description: str,
    action_type: str | None = None,
    urgency: str | None = None,
    deadline_date: datetime | None = None,
) -> Action:
    action = Action(
        user_id=user_id,
        conversation_id=conversation_id,
        source_type=source_type,
        source_id=source_id,
        action_type=action_type,
        description=description,
        urgency=urgency,
        deadline_date=deadline_date,
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def mark_action_status(session: Session, *, action_id: str, status: str) -> Action:
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUSES)}, got {status!r}")
    action = session.get(Action, action_id)
    if action is None:
        raise ValueError(f"action {action_id!r} not found")
    action.status = status
    if status == "done":
        action.completed_at = datetime.utcnow()
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def list_pending_actions_for_user(session: Session, user_id: str) -> list[Action]:
    statement = (
        select(Action)
        .where(Action.user_id == user_id, Action.status.in_(("pending", "in_progress")))
        .order_by(Action.deadline_date.asc().nullslast(), Action.created_at.asc())
    )
    return list(session.scalars(statement))


def list_actions_for_source(session: Session, *, source_type: str, source_id: str) -> list[Action]:
    statement = (
        select(Action)
        .where(Action.source_type == source_type, Action.source_id == source_id)
        .order_by(Action.created_at.asc())
    )
    return list(session.scalars(statement))
