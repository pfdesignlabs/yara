from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.message import Message
from app.services.message_service import get_recent_messages_for_conversation

HISTORY_LIMIT = 10

settings = get_settings()
llm = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)


class RouterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _process(state: RouterState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


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


def run_router(session: Session, conversation_id: str) -> str:
    history = get_recent_messages_for_conversation(
        session,
        conversation_id=conversation_id,
        limit=HISTORY_LIMIT,
    )
    langchain_history = _db_messages_to_langchain(history)

    result = agent.invoke({"messages": langchain_history})
    return result["messages"][-1].content
