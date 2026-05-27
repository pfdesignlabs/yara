"""LLM-facing tool wrappers around the action_service CRUD."""

from langchain_core.tools import tool

from app.db.session import SessionLocal
from app.services.action_service import mark_action_status


@tool
def mark_action_done(action_id: str) -> str:
    """Mark an action as completed.

    Use this when the user confirms they did the suggested step (or
    explicitly skipped it and considers it done). Sets the action's
    `status` to `'done'` and stamps `completed_at`.
    """
    with SessionLocal() as session:
        action = mark_action_status(session, action_id=action_id, status="done")
    return f"Action {action.id} marked as done."
