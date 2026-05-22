from typing import Literal, TypedDict


class RecentMessage(TypedDict):
    direction: Literal["inbound", "outbound", "system"]
    message_type: str
    content_text: str | None
    created_at: str


class GuidedJourneyState(TypedDict, total=False):
    user_id: str
    conversation_id: str
    message_id: str
    thread_id: str

    journey_key: str
    preferred_language: str | None
    inferred_language: str | None
    current_message_text: str | None
    recent_messages: list[RecentMessage]

    active_workflow_type: str | None
    active_workflow_step: str | None
    situation_summary: str | None

    facts: dict[str, object]
    blockers: list[str]
    recommended_route: str | None
    next_question_key: str | None
    reply_text: str | None
