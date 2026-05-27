import logging
from datetime import datetime
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.user import User
from app.prompts import get, get_node_prompt
from app.services.attachment_service import get_recent_documents_for_doc_helper
from app.services.message_service import get_recent_messages_for_conversation
from app.services.workflow_state_service import create_intake, get_latest_intake
from app.workflows._llm import llm_for_node
from app.workflows.document_helper import document_helper_node
from app.workflows.intake import intake_node, state_extractor_node

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
ROUTER_VERSION = "router_v3"


class RouterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    slots: dict
    user_id: str
    intake_done: bool
    documents: list[dict]
    next: str | None


def _tag(response: AIMessage, node_name: str) -> AIMessage:
    response.additional_kwargs["source_node"] = node_name
    return response


def _router_node(state: RouterState) -> dict:
    if not state["intake_done"]:
        return {"next": "intake_flow"}
    if state["slots"].get("matched_workflow") == "document_helper":
        return {"next": "doc_helper"}
    return {"next": "chat"}


def _chat_node(state: RouterState) -> dict:
    system = SystemMessage(content=get_node_prompt("chat_node"))
    response = llm_for_node("chat_node").invoke([system, *state["messages"]])
    return {"messages": [_tag(response, "chat_node")]}


def _build_agent():
    graph = StateGraph(RouterState)
    graph.add_node("router", _router_node)
    graph.add_node("state_extractor", state_extractor_node)
    graph.add_node("intake_node", intake_node)
    graph.add_node("document_helper_node", document_helper_node)
    graph.add_node("chat_node", _chat_node)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        lambda s: s["next"],
        {
            "intake_flow": "state_extractor",
            "doc_helper": "document_helper_node",
            "chat": "chat_node",
        },
    )
    graph.add_edge("state_extractor", "intake_node")
    graph.add_edge("intake_node", END)
    graph.add_edge("document_helper_node", END)
    graph.add_edge("chat_node", END)
    return graph.compile()


agent = _build_agent()


def _db_messages_to_langchain(messages: list[Message]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        if not message.content_text:
            continue
        if message.direction == "inbound":
            converted.append(HumanMessage(content=message.content_text))
        elif message.direction == "outbound":
            converted.append(AIMessage(content=message.content_text))
    return converted


def _documents_snapshot(session: Session, conversation_id: str) -> list[dict]:
    return [
        {
            "id": doc.id,
            "mime_type": doc.mime_type,
            "file_storage_path": doc.file_storage_path,
            "extracted_text": doc.extracted_text,
        }
        for doc in get_recent_documents_for_doc_helper(session, conversation_id)
    ]


def run_router(session: Session, conversation_id: str, user_id: str) -> tuple[str, str | None]:
    try:
        history = get_recent_messages_for_conversation(
            session,
            conversation_id=conversation_id,
            limit=HISTORY_LIMIT,
        )
        langchain_history = _db_messages_to_langchain(history)

        user = session.get(User, user_id)
        intake = get_latest_intake(session, user_id)
        if intake is None:
            intake = create_intake(session, user_id=user_id, conversation_id=conversation_id)
            intake_done = False
        else:
            intake_done = intake.completed_at is not None

        documents = (
            _documents_snapshot(session, conversation_id)
            if intake_done and intake.state_json.get("matched_workflow") == "document_helper"
            else []
        )

        initial_state: RouterState = {
            "messages": langchain_history,
            "slots": dict(intake.state_json or {}),
            "user_id": user_id,
            "intake_done": intake_done,
            "documents": documents,
            "next": None,
        }

        result = agent.invoke(
            initial_state,
            config={
                "run_name": ROUTER_VERSION,
                "metadata": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                },
            },
        )
        last_message = result["messages"][-1]
        source_node = last_message.additional_kwargs.get("source_node")
        reply = last_message.content
        new_slots = result["slots"]

        if not intake_done:
            intake.state_json = new_slots
            if new_slots.get("matched_workflow") is not None:
                intake.completed_at = datetime.utcnow()
                intake.current_step = "completed"
                pref = new_slots.get("preferred_language")
                if pref and user.preferred_language != pref:
                    user.preferred_language = pref
                    session.add(user)
            session.add(intake)
            session.commit()

        return reply, source_node
    except Exception:
        logger.exception(
            "Router failed for conversation_id=%s user_id=%s — returning fallback message",
            conversation_id,
            user_id,
        )
        return get("fallbacks.llm_error"), "error_fallback"
