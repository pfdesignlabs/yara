from pathlib import Path
from pprint import pprint
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.workflows.intake_router.graph import intake_router_graph


def main() -> None:
    sample_state = {
        "user_id": "user-123",
        "conversation_id": "conversation-123",
        "message_id": "message-123",
        "thread_id": "conversation-123",
        "is_new_user": True,
        "is_new_conversation": True,
        "has_active_workflow": False,
        "display_name": "Jochem",
        "preferred_language": None,
        "inferred_language": None,
        "should_confirm_language": True,
        "current_message_type": "text",
        "current_message_text": "Hallo Yara",
        "current_message_media_url": None,
        "current_message_media_content_type": None,
        "recent_messages": [],
        "active_workflow_type": None,
        "active_workflow_step": None,
        "workflow_status": None,
        "workflow_type_candidate": None,
        "should_start_new_workflow": False,
        "should_continue_existing_workflow": False,
        "missing_information": [],
        "intake_complete": False,
        "reply_text": None,
        "next_expected_input": None,
        "transition_to_workflow": None,
    }

    result = intake_router_graph.invoke(sample_state)
    pprint(result)


if __name__ == "__main__":
    main()
