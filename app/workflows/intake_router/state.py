from typing import Literal, TypedDict


class RecentMessage(TypedDict):
    direction: Literal["inbound", "outbound", "system"]
    message_type: str
    content_text: str | None
    created_at: str


class IntakeRouterState(TypedDict, total=False):
    # Identity
    user_id: str
    conversation_id: str
    message_id: str
    thread_id: str

    # Session flags
    is_new_user: bool
    is_new_conversation: bool
    has_active_workflow: bool
    is_low_information_message: bool

    # User context
    display_name: str | None
    preferred_language: str | None
    inferred_language: str | None
    should_confirm_language: bool

    # Current message
    current_message_type: str
    current_message_text: str | None
    current_message_media_url: str | None
    current_message_media_content_type: str | None

    # Recent conversation context
    recent_messages: list[RecentMessage]

    # Current workflow context
    active_workflow_type: str | None
    active_workflow_step: str | None
    workflow_status: str | None
    situation_summary: str | None
    open_loop: str | None
    guided_journey_facts: dict[str, object] | None

    # Routing and reasoning
    workflow_type_candidate: str | None
    should_start_new_workflow: bool
    should_continue_existing_workflow: bool
    missing_information: list[str]
    intake_complete: bool

    # Response plan
    reply_text: str | None
    next_expected_input: str | None
    transition_to_workflow: str | None
