from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow_state import WorkflowState
from app.workflows.guided_journey.state import GuidedJourneyState
from app.workflows.intake_router.state import IntakeRouterState


def get_active_workflow_for_conversation(session: Session, conversation_id: str) -> WorkflowState | None:
    statement = (
        select(WorkflowState)
        .where(WorkflowState.conversation_id == conversation_id)
        .where(WorkflowState.status == "active")
        .order_by(WorkflowState.updated_at.desc())
    )
    return session.scalars(statement).first()


def start_workflow(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    workflow_type: str,
    current_step: str,
    state_json: dict[str, Any] | None = None,
) -> WorkflowState:
    workflow = WorkflowState(
        user_id=user_id,
        conversation_id=conversation_id,
        workflow_type=workflow_type,
        current_step=current_step,
        status="active",
        state_json=state_json or {},
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def update_workflow_state(
    session: Session,
    workflow: WorkflowState,
    *,
    workflow_type: str | None = None,
    current_step: str | None = None,
    status: str | None = None,
    state_json: dict[str, Any] | None = None,
    completed: bool = False,
) -> WorkflowState:
    if workflow_type is not None:
        workflow.workflow_type = workflow_type
    if current_step is not None:
        workflow.current_step = current_step
    if status is not None:
        workflow.status = status
    if state_json is not None:
        workflow.state_json = state_json

    workflow.updated_at = datetime.utcnow()

    if completed:
        workflow.status = "completed"
        workflow.completed_at = datetime.utcnow()

    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def sync_workflow_from_intake_result(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    active_workflow: WorkflowState | None,
    state: IntakeRouterState,
) -> WorkflowState:
    workflow_type = state.get("transition_to_workflow") or state.get("workflow_type_candidate") or "general_intake"
    current_step = _step_from_state(state)
    state_json = _build_workflow_state_json(state)

    if active_workflow is None:
        return start_workflow(
            session,
            user_id=user_id,
            conversation_id=conversation_id,
            workflow_type=workflow_type,
            current_step=current_step,
            state_json=state_json,
        )

    return update_workflow_state(
        session,
        active_workflow,
        workflow_type=workflow_type,
        current_step=current_step,
        state_json=state_json,
        status="active",
        completed=bool(state.get("intake_complete")),
    )


def _step_from_state(state: IntakeRouterState) -> str:
    next_expected_input = state.get("next_expected_input")
    mapping = {
        "user_situation": "ask_situation",
        "document_upload": "await_document",
        "digid_problem_description": "ask_digid_problem",
        "document_processing": "document_received",
    }
    return mapping.get(next_expected_input, "intake_in_progress")


def _build_workflow_state_json(state: IntakeRouterState) -> dict[str, Any]:
    return {
        "language_confirmed": state.get("preferred_language") is not None,
        "inferred_language": state.get("inferred_language"),
        "preferred_language": state.get("preferred_language"),
        "situation_summary": state.get("situation_summary"),
        "open_loop": state.get("open_loop"),
        "guided_journey_key": state.get("guided_journey_key"),
        "guided_journey_facts": state.get("guided_journey_facts"),
        "has_document": state.get("current_message_type") in {"image", "document"},
        "journey_candidate": state.get("workflow_type_candidate"),
        "intake_complete": state.get("intake_complete", False),
        "missing_information": state.get("missing_information", []),
    }


def sync_workflow_from_guided_journey_result(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    active_workflow: WorkflowState | None,
    state: GuidedJourneyState,
) -> WorkflowState:
    current_step = state.get("next_question_key") or state.get("recommended_route") or "guided_journey_in_progress"
    state_json = {
        "journey_key": state.get("journey_key"),
        "preferred_language": state.get("preferred_language"),
        "inferred_language": state.get("inferred_language"),
        "situation_summary": state.get("situation_summary"),
        "facts": state.get("facts", {}),
        "blockers": state.get("blockers", []),
        "recommended_route": state.get("recommended_route"),
        "next_question_key": state.get("next_question_key"),
    }

    if active_workflow is None:
        return start_workflow(
            session,
            user_id=user_id,
            conversation_id=conversation_id,
            workflow_type="guided_journey",
            current_step=current_step,
            state_json=state_json,
        )

    return update_workflow_state(
        session,
        active_workflow,
        workflow_type="guided_journey",
        current_step=current_step,
        state_json=state_json,
        status="active",
        completed=False,
    )
