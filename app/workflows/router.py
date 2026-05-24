import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.message import Message
from app.prompts import get, get_node_prompt
from app.services.message_service import get_recent_messages_for_conversation

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
ROUTER_VERSION = "router_v1"

settings = get_settings()
llm = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)


class RouterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _tag(response: AIMessage, node_name: str) -> AIMessage:
    response.additional_kwargs["source_node"] = node_name
    return response


def _process(state: RouterState) -> dict:
    system = SystemMessage(content=get_node_prompt("chat_node"))
    response = llm.invoke([system, *state["messages"]])
    return {"messages": [_tag(response, "process")]}


def _build_agent():
    graph = StateGraph(RouterState)
    graph.add_node("process", _process)
    graph.add_edge(START, "process")
    graph.add_edge("process", END)
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


def run_router(session: Session, conversation_id: str, user_id: str) -> tuple[str, str | None]:
    try:
        history = get_recent_messages_for_conversation(
            session,
            conversation_id=conversation_id,
            limit=HISTORY_LIMIT,
        )
        langchain_history = _db_messages_to_langchain(history)

        result = agent.invoke(
            {"messages": langchain_history},
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
        return last_message.content, source_node
    except Exception:
        logger.exception(
            "Router failed for conversation_id=%s user_id=%s — returning fallback message",
            conversation_id,
            user_id,
        )
        return get("fallbacks.llm_error"), "error_fallback"
