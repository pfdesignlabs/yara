"""Intake client speaker — generates the conversational reply for an intake turn.

The slot update is produced by `state_extractor_node` (in
`intake_extractor.py`) earlier in the same LangGraph turn; this module
only renders the reply.
"""

import json

from langchain_core.messages import AIMessage, SystemMessage

from app.prompts import get_node_prompt
from app.workflows._llm import llm_for_node


def intake_node(state: dict) -> dict:
    """Produce the conversational reply for the intake turn."""
    base = get_node_prompt("intake_node")
    state_dump = json.dumps(state["slots"], ensure_ascii=False, indent=2)
    system = SystemMessage(content=f"{base}\n\nHuidige state:\n{state_dump}")
    response: AIMessage = llm_for_node("intake_node").invoke([system, *state["messages"]])
    response.additional_kwargs["source_node"] = "intake_node"
    return {"messages": [response]}
