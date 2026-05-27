"""Intake workflow nodes: state extractor (internal) and intake (client).

The extractor produces a structured update for the slot dict on every turn;
the intake node generates the conversational reply based on the resulting
state. Both prompts live in `app/prompts/prompts.yaml`.
"""

import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import get_settings
from app.prompts import get_node_config, get_node_prompt

_settings = get_settings()

_intake_cfg = get_node_config("intake_node")
_extractor_cfg = get_node_config("state_extractor_node")

_intake_llm = ChatOpenAI(
    model=_intake_cfg["model"],
    temperature=_intake_cfg["temperature"],
    api_key=_settings.openai_api_key,
)
_extractor_llm = ChatOpenAI(
    model=_extractor_cfg["model"],
    temperature=_extractor_cfg["temperature"],
    api_key=_settings.openai_api_key,
)


class ExtractedState(BaseModel):
    information_need: str | None = None
    preferred_language: str | None = None
    family_composition: str | None = None
    country_of_origin: str | None = None
    residence_status: str | None = None
    dutch_proficiency: Literal["fluent", "limited"] | None = None
    matched_workflow: Literal["document_helper", "none"] | None = None


_extractor_structured = _extractor_llm.with_structured_output(ExtractedState)


def state_extractor_node(state: dict) -> dict:
    """Read messages + current slots, return merged slots."""
    system = SystemMessage(content=get_node_prompt("state_extractor_node"))
    current = ExtractedState(**state["slots"])
    instruction = HumanMessage(
        content=(
            "Huidige state:\n"
            f"{current.model_dump_json(indent=2)}\n\n"
            "Update de slots op basis van het volledige gesprek hierboven. "
            "Behoud eerder gevulde slots, vul nieuwe in zodra de gebruiker er "
            "iets over zegt."
        )
    )
    extracted = _extractor_structured.invoke([system, *state["messages"], instruction])
    merged = {
        field: (
            getattr(extracted, field)
            if getattr(extracted, field) is not None
            else state["slots"].get(field)
        )
        for field in ExtractedState.model_fields
    }
    return {"slots": merged}


def intake_node(state: dict) -> dict:
    """Produce the conversational reply for the intake turn."""
    base = get_node_prompt("intake_node")
    state_dump = json.dumps(state["slots"], ensure_ascii=False, indent=2)
    system = SystemMessage(content=f"{base}\n\nHuidige state:\n{state_dump}")
    response: AIMessage = _intake_llm.invoke([system, *state["messages"]])
    response.additional_kwargs["source_node"] = "intake_node"
    return {"messages": [response]}
