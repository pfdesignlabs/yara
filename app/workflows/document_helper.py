"""Document helper specialist: explains an uploaded PDF or photo(s) and
surfaces the actions extracted by `extract_doc_metadata_node`."""

import base64
import logging
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langcodes import Language
from sqlalchemy.orm import Session

from app.models.action import Action
from app.prompts import get_node_prompt
from app.tools import TOOL_REGISTRY, tools_for_node
from app.workflows._llm import llm_for_node
from app.workflows.doc_metadata import extract_and_persist_doc_metadata

logger = logging.getLogger(__name__)

# Cap PDF text to keep the prompt within a comfortable context budget.
# ~24k chars ≈ 6k tokens, covers most multi-page letters.
_MAX_PDF_TEXT_CHARS = 24_000

# Safety bound on the tool-call → ToolMessage → LLM loop.
_MAX_TOOL_ITERATIONS = 3


def _language_name(code: str) -> str:
    try:
        return Language.get(code).display_name("nl")
    except Exception:
        return code


def _is_followup(messages: list[BaseMessage]) -> bool:
    """True when a prior AI turn exists — current message is a follow-up."""
    return any(isinstance(m, AIMessage) for m in messages)


def _intent(language_name: str, is_followup: bool) -> str:
    if is_followup:
        return (
            f"De gebruiker heeft hierboven een vervolgvraag gesteld. Beantwoord die "
            f"kort en specifiek (1-3 zinnen) in het {language_name}. Herhaal de "
            f"uitleg van het document NIET — die heb je al gegeven."
        )
    return (
        f"Leg in het {language_name} (B1-niveau) uit wat erin staat: kernpunt, "
        f"belangrijke deadlines/bedragen/instanties, en één concrete vervolgstap."
    )


def _reminder_reply_brief(snapshot: dict) -> str:
    """Render reminder-reply context for the doc_helper LLM."""
    lines = ["\n\n---REMINDER-REPLY CONTEXT---"]
    lines.append("De gebruiker reageert op een eerder verstuurde reminder.")
    lines.append(f"- Reminder verzonden op: {snapshot.get('sent_at') or 'onbekend'}")
    lines.append(f"- Reminder-tekst: {snapshot.get('body_template')!r}")
    if snapshot.get("action_id"):
        lines.append(f"- Gekoppelde actie-id: {snapshot['action_id']}")
        lines.append(f"- Actie-beschrijving: {snapshot.get('action_description')!r}")
        lines.append(f"- Huidige actie-status: {snapshot.get('action_status')}")
    lines.append("---EINDE REMINDER-REPLY CONTEXT---")
    return "\n".join(lines)


def _today_line() -> str:
    """Anchor the LLM to today's date AND time so it can compute relative
    moments (morgen / volgende week / +5 minuten) when scheduling reminders.
    Without this the model guesses, sometimes weeks off."""
    now = datetime.now(UTC)
    return (
        f"\n\nHuidig moment: {now.isoformat(timespec='seconds')} (UTC). "
        f"Gebruik dit als anker voor relatieve tijden."
    )


def _actions_brief(actions: list[Action]) -> str:
    """Render persisted actions for the doc_helper LLM as context.

    Each line leads with `id=<uuid>` so the LLM has the real action_id to
    pass to `mark_action_done` / `create_reminder` (`target_id`). Without
    this exposure the LLM was hallucinating the action_type as the id.
    """
    if not actions:
        return ""
    lines = ["\n\n---ACTIES (geëxtraheerd uit het document)---"]
    for a in actions:
        deadline = a.deadline_date.date().isoformat() if a.deadline_date else "geen deadline"
        atype = a.action_type or "—"
        lines.append(
            f"- id={a.id} status={a.status} urgency={a.urgency} type={atype} "
            f"deadline={deadline} | {a.description}"
        )
    lines.append("---EINDE ACTIES---")
    return "\n".join(lines)


def _inject_runtime_args(
    tool, args: dict, *, session: Session, user_id: str, conversation_id: str
) -> dict:
    """Fill the InjectedToolArg slots the LLM doesn't see in the tool schema."""
    schema_fields = set(tool.args_schema.model_fields.keys())
    merged = dict(args)
    if "session" in schema_fields:
        merged["session"] = session
    if "user_id" in schema_fields:
        merged["user_id"] = user_id
    if "conversation_id" in schema_fields:
        merged["conversation_id"] = conversation_id
    return merged


def _execute_tool_calls(
    response: AIMessage,
    *,
    session: Session,
    user_id: str,
    conversation_id: str,
) -> list[ToolMessage]:
    """Run every tool the LLM asked for, surfacing errors as ToolMessages."""
    tool_messages: list[ToolMessage] = []
    for call in response.tool_calls:
        name = call["name"]
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            tool_messages.append(
                ToolMessage(
                    content=f"Tool error: unknown tool {name!r}",
                    tool_call_id=call["id"],
                    status="error",
                )
            )
            continue
        try:
            args = _inject_runtime_args(
                tool,
                call["args"],
                session=session,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            result = tool.invoke(args)
            tool_messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        except Exception as e:
            logger.exception("doc_helper tool %r failed", name)
            tool_messages.append(
                ToolMessage(
                    content=f"Tool error: {e}",
                    tool_call_id=call["id"],
                    status="error",
                )
            )
    return tool_messages


def _invoke_with_tool_loop(
    llm,
    messages: list[BaseMessage],
    *,
    session: Session,
    user_id: str,
    conversation_id: str,
) -> AIMessage:
    """LLM call + tool-execution loop. Stops when no more tool_calls or after a few rounds."""
    response: AIMessage = llm.invoke(messages)
    for _ in range(_MAX_TOOL_ITERATIONS):
        if not response.tool_calls:
            return response
        tool_messages = _execute_tool_calls(
            response,
            session=session,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        messages = [*messages, response, *tool_messages]
        response = llm.invoke(messages)
    if response.tool_calls:
        logger.warning(
            "doc_helper hit _MAX_TOOL_ITERATIONS=%d with tool_calls still pending",
            _MAX_TOOL_ITERATIONS,
        )
    return response


def document_helper_node(state: dict) -> dict:
    """Explain the latest document(s), or ask for one if none has been sent yet."""
    base_llm = llm_for_node("document_helper_node")
    tools = tools_for_node("document_helper_node")
    llm = base_llm.bind_tools(tools) if tools else base_llm
    system = SystemMessage(content=get_node_prompt("document_helper_node"))

    documents: list[dict] = state.get("documents") or []
    preferred_language = (state.get("slots") or {}).get("preferred_language") or "nl"
    language_name = _language_name(preferred_language)
    is_followup = _is_followup(state["messages"])

    if not documents:
        instruction = HumanMessage(
            content=(
                f"De gebruiker heeft nog geen document gestuurd. Vraag er beleefd om "
                f"in het {language_name}. Eén zin volstaat. Noem dat het een PDF of "
                f"foto mag zijn, en dat ze voor brieven van meerdere pagina's het "
                f"beste een PDF kunnen sturen of alle pagina's één voor één na "
                f"elkaar."
            )
        )
        response = _invoke_with_tool_loop(
            llm,
            [system, *state["messages"], instruction],
            session=state["session"],
            user_id=state["user_id"],
            conversation_id=state["conversation_id"],
        )
        response.additional_kwargs["source_node"] = "document_helper_node"
        return {"messages": [response]}

    actions = extract_and_persist_doc_metadata(
        state["session"],
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
        documents=documents,
    )

    reminder_reply = state.get("replying_to_reminder")
    first_mime = documents[0]["mime_type"]
    if first_mime.startswith("image/"):
        instruction = _vision_instruction(
            documents, language_name, is_followup, actions, reminder_reply
        )
    else:
        instruction = _pdf_instruction(
            documents[0], language_name, is_followup, actions, reminder_reply
        )

    response = _invoke_with_tool_loop(
        llm,
        [system, *state["messages"], instruction],
        session=state["session"],
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
    )
    response.additional_kwargs["source_node"] = "document_helper_node"
    return {"messages": [response]}


def _pdf_instruction(
    document: dict,
    language_name: str,
    is_followup: bool,
    actions: list[Action],
    reminder_reply: dict | None = None,
) -> HumanMessage:
    text = (document.get("extracted_text") or "").strip()
    if not text:
        return HumanMessage(
            content=(
                f"De gebruiker stuurde een PDF, maar de tekst is niet uitleesbaar "
                f"(leeg of versleuteld). Leg dat uit in het {language_name} en vraag "
                f"of ze een duidelijke foto van het document kunnen sturen."
            )
        )
    truncated = text[:_MAX_PDF_TEXT_CHARS]
    truncation_notice = ""
    if len(text) > _MAX_PDF_TEXT_CHARS:
        truncation_notice = (
            " Het document is lang — alleen het begin is hieronder weergegeven. "
            "Meld dat in je antwoord en nodig de gebruiker uit om gericht vragen te "
            "stellen over een specifiek deel."
        )
    reminder_block = _reminder_reply_brief(reminder_reply) if reminder_reply else ""
    return HumanMessage(
        content=(
            f"Hieronder de tekst van een document dat de gebruiker heeft gestuurd. "
            f"{_intent(language_name, is_followup)}{truncation_notice}"
            f"{_today_line()}"
            f"{_actions_brief(actions)}{reminder_block}\n"
            f"\n---DOCUMENT TEKST---\n{truncated}\n---EINDE---"
        )
    )


def _vision_instruction(
    documents: list[dict],
    language_name: str,
    is_followup: bool,
    actions: list[Action],
    reminder_reply: dict | None = None,
) -> HumanMessage:
    pages = len(documents)
    if pages == 1:
        framing = "Hieronder een foto van een document dat de gebruiker heeft gestuurd."
    else:
        framing = (
            f"Hieronder {pages} foto's van een document dat de gebruiker heeft "
            f"gestuurd, in volgorde van pagina 1 tot pagina {pages}. Behandel ze als "
            f"één document."
        )

    reminder_block = _reminder_reply_brief(reminder_reply) if reminder_reply else ""
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"{framing} {_intent(language_name, is_followup)} Als delen "
                f"onleesbaar zijn, zeg dat eerlijk in plaats van te gokken."
                f"{_today_line()}"
                f"{_actions_brief(actions)}{reminder_block}"
            ),
        }
    ]
    for doc in documents:
        file_path = Path(doc["file_storage_path"])
        image_bytes = file_path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{doc['mime_type']};base64,{b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    return HumanMessage(content=content)
