from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.workflow_state import WorkflowState


def get_latest_intake(session: Session, user_id: str) -> WorkflowState | None:
    statement = (
        select(WorkflowState)
        .where(
            WorkflowState.user_id == user_id,
            WorkflowState.workflow_type == "intake",
        )
        .order_by(desc(WorkflowState.started_at))
        .limit(1)
    )
    return session.scalar(statement)


def create_intake(session: Session, user_id: str, conversation_id: str) -> WorkflowState:
    intake = WorkflowState(
        user_id=user_id,
        conversation_id=conversation_id,
        workflow_type="intake",
        current_step="collecting",
        state_json={},
    )
    session.add(intake)
    session.commit()
    session.refresh(intake)
    return intake
