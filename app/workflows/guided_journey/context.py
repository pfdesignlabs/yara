from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.models.workflow_state import WorkflowState
from app.workflows.guided_journey.state import GuidedJourneyState, RecentMessage


def build_guided_journey_state(
    *,
    journey_key: str,
    user: User,
    conversation: Conversation,
    message: Message,
    recent_messages: list[Message],
    active_workflow: WorkflowState | None,
    inferred_language: str | None,
    situation_summary: str | None,
) -> GuidedJourneyState:
    workflow_state = active_workflow.state_json if active_workflow and active_workflow.state_json else {}

    return {
        "user_id": user.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
        "thread_id": conversation.id,
        "journey_key": journey_key,
        "preferred_language": user.preferred_language,
        "inferred_language": inferred_language,
        "current_message_text": message.content_text,
        "recent_messages": [_serialize_message(item) for item in recent_messages],
        "active_workflow_type": active_workflow.workflow_type if active_workflow else None,
        "active_workflow_step": active_workflow.current_step if active_workflow else None,
        "situation_summary": situation_summary or workflow_state.get("situation_summary"),
        "facts": workflow_state.get("facts", {}),
        "blockers": workflow_state.get("blockers", []),
        "recommended_route": workflow_state.get("recommended_route"),
        "next_question_key": workflow_state.get("next_question_key"),
        "reply_text": None,
    }


def _serialize_message(message: Message) -> RecentMessage:
    return {
        "direction": message.direction,
        "message_type": message.message_type,
        "content_text": message.content_text,
        "created_at": message.created_at.isoformat(),
    }
