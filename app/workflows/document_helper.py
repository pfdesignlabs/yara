"""Document helper specialist: explains an uploaded PDF or photo(s)."""

import base64
import logging
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langcodes import Language

from app.prompts import get_node_prompt
from app.workflows._llm import llm_for_node

logger = logging.getLogger(__name__)

# Cap PDF text to keep the prompt within a comfortable context budget.
# ~24k chars ≈ 6k tokens, covers most multi-page letters.
_MAX_PDF_TEXT_CHARS = 24_000


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


def document_helper_node(state: dict) -> dict:
    """Explain the latest document(s), or ask for one if none has been sent yet."""
    llm = llm_for_node("document_helper_node")
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
        response: AIMessage = llm.invoke([system, *state["messages"], instruction])
        response.additional_kwargs["source_node"] = "document_helper_node"
        return {"messages": [response]}

    first_mime = documents[0]["mime_type"]
    if first_mime.startswith("image/"):
        instruction = _vision_instruction(documents, language_name, is_followup)
    else:
        instruction = _pdf_instruction(documents[0], language_name, is_followup)

    response = llm.invoke([system, *state["messages"], instruction])
    response.additional_kwargs["source_node"] = "document_helper_node"
    return {"messages": [response]}


def _pdf_instruction(document: dict, language_name: str, is_followup: bool) -> HumanMessage:
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
    return HumanMessage(
        content=(
            f"Hieronder de tekst van een document dat de gebruiker heeft gestuurd. "
            f"{_intent(language_name, is_followup)}{truncation_notice}\n"
            f"\n---DOCUMENT TEKST---\n{truncated}\n---EINDE---"
        )
    )


def _vision_instruction(
    documents: list[dict], language_name: str, is_followup: bool
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

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"{framing} {_intent(language_name, is_followup)} Als delen "
                f"onleesbaar zijn, zeg dat eerlijk in plaats van te gokken."
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
