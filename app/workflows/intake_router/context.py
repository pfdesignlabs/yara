from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.models.workflow_state import WorkflowState
from app.workflows.intake_router.state import IntakeRouterState, RecentMessage


def build_intake_router_state(
    *,
    user: User,
    conversation: Conversation,
    message: Message,
    recent_messages: list[Message],
    active_workflow: WorkflowState | None,
    is_new_user: bool,
    is_new_conversation: bool,
) -> IntakeRouterState:
    inferred_language = None
    should_confirm_language = user.preferred_language is None
    workflow_state = active_workflow.state_json if active_workflow and active_workflow.state_json else {}

    return {
        "user_id": user.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
        "thread_id": conversation.id,
        "is_new_user": is_new_user,
        "is_new_conversation": is_new_conversation,
        "has_active_workflow": active_workflow is not None,
        "is_low_information_message": False,
        "display_name": user.display_name,
        "preferred_language": user.preferred_language,
        "inferred_language": inferred_language,
        "should_confirm_language": should_confirm_language,
        "current_message_type": message.message_type,
        "current_message_text": message.content_text,
        "current_message_media_url": message.media_storage_path,
        "current_message_media_content_type": message.media_mime_type,
        "recent_messages": [_serialize_message(item) for item in recent_messages],
        "active_workflow_type": active_workflow.workflow_type if active_workflow else None,
        "active_workflow_step": active_workflow.current_step if active_workflow else None,
        "workflow_status": active_workflow.status if active_workflow else None,
        "situation_summary": workflow_state.get("situation_summary"),
        "open_loop": workflow_state.get("open_loop"),
        "guided_journey_facts": workflow_state.get("facts") or workflow_state.get("guided_journey_facts"),
        "workflow_type_candidate": None,
        "should_start_new_workflow": active_workflow is None,
        "should_continue_existing_workflow": active_workflow is not None,
        "missing_information": [],
        "intake_complete": False,
        "reply_text": None,
        "next_expected_input": None,
        "transition_to_workflow": None,
    }


def _serialize_message(message: Message) -> RecentMessage:
    return {
        "direction": message.direction,
        "message_type": message.message_type,
        "content_text": message.content_text,
        "created_at": message.created_at.isoformat(),
    }
