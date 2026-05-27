"""Structured-output extractor that turns a document into actions.

Internal node (`extract_doc_metadata_node` in `prompts.yaml`) — separate
from the client-facing `document_helper_node` because it has a different
model, temperature, and prompt. Runs ONCE per new Document; on later
doc_helper turns the persisted actions are read from the DB instead.
"""

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.action import Action
from app.prompts import get_node_prompt
from app.services.action_service import create_action, list_actions_for_source
from app.workflows._llm import llm_for_node

logger = logging.getLogger(__name__)

SOURCE_TYPE = "document_helper"
_MAX_PDF_TEXT_CHARS = 24_000

Urgency = Literal["today", "this_week", "this_month", "no_deadline"]


class ActionDraft(BaseModel):
    description: str = Field(
        description=(
            "Concrete, actionable next step the user must take. One sentence, "
            "imperative mood (e.g. 'Dien bezwaar in tegen de afwijzing')."
        )
    )
    action_type: str | None = Field(
        default=None,
        description=(
            "Short category tag, e.g. 'bezwaar', 'betalen', 'verlenging_aanvragen', "
            "'afspraak_maken'. Lowercase snake_case-style. Null if no clear category."
        ),
    )
    urgency: Urgency = Field(
        description=(
            "Time pressure on this specific action. 'today' for same-day, "
            "'this_week' for ≤7 days, 'this_month' for ≤30 days, 'no_deadline' "
            "for open-ended."
        )
    )
    deadline_date: datetime | None = Field(
        default=None,
        description=(
            "Hard deadline date for this action if mentioned in the document. "
            "ISO 8601 datetime. Null if no explicit deadline."
        ),
    )


class DocMetadata(BaseModel):
    document_type: str = Field(
        description=(
            "Short free-text label for what kind of document this is, in Dutch. "
            "Examples: 'afwijzing bijstandsaanvraag', 'aanmaning', 'verlengingsbesluit', "
            "'oproep', 'beschikking', 'rappel'."
        )
    )
    urgency: Urgency = Field(description="Overall time pressure on the document as a whole.")
    deadline_date: datetime | None = Field(
        default=None,
        description=(
            "Single hardest deadline mentioned in the document, ISO 8601. Null if "
            "no explicit overall deadline."
        ),
    )
    actions: list[ActionDraft] = Field(
        default_factory=list,
        description=(
            "Concrete next steps the recipient must take. Order from most to least "
            "urgent. Empty list if the document is purely informational with no "
            "required action."
        ),
    )


def _pdf_instruction(document: dict) -> HumanMessage:
    text = (document.get("extracted_text") or "").strip()
    truncated = text[:_MAX_PDF_TEXT_CHARS]
    return HumanMessage(
        content=(
            "Analyseer het document hieronder en lever de gestructureerde metadata.\n"
            f"\n---DOCUMENT TEKST---\n{truncated}\n---EINDE---"
        )
    )


def _vision_instruction(documents: list[dict]) -> HumanMessage:
    pages = len(documents)
    if pages == 1:
        framing = "Analyseer de foto van een document hieronder."
    else:
        framing = (
            f"Analyseer de {pages} foto's hieronder, in volgorde van pagina 1 tot "
            f"pagina {pages}. Behandel ze als één document."
        )
    content: list[dict] = [
        {"type": "text", "text": framing + " Lever de gestructureerde metadata."}
    ]
    for doc in documents:
        image_bytes = Path(doc["file_storage_path"]).read_bytes()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{doc['mime_type']};base64,{b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    return HumanMessage(content=content)


def _build_instruction(documents: list[dict]) -> HumanMessage | None:
    first_mime = documents[0]["mime_type"]
    if first_mime.startswith("image/"):
        return _vision_instruction(documents)
    text = (documents[0].get("extracted_text") or "").strip()
    if not text:
        return None
    return _pdf_instruction(documents[0])


def extract_doc_metadata(documents: list[dict]) -> DocMetadata | None:
    """Run the structured-output extractor on the (multi-page) document.

    Returns None when the document has no readable text and no image pages.
    """
    instruction = _build_instruction(documents)
    if instruction is None:
        return None
    llm = llm_for_node("extract_doc_metadata_node").with_structured_output(DocMetadata)
    system = SystemMessage(content=get_node_prompt("extract_doc_metadata_node"))
    return llm.invoke([system, instruction])


def extract_and_persist_doc_metadata(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    documents: list[dict],
) -> list[Action]:
    """Idempotently extract metadata for the primary document and persist actions.

    Skips extraction entirely when actions already exist for the document's id —
    so re-entries from later doc_helper turns are cheap.
    """
    if not documents:
        return []

    primary_id = documents[0]["id"]
    existing = list_actions_for_source(session, source_type=SOURCE_TYPE, source_id=primary_id)
    if existing:
        return existing

    metadata = extract_doc_metadata(documents)
    if metadata is None:
        logger.warning(
            "extract_doc_metadata returned None for document %s (no text + no images)",
            primary_id,
        )
        return []

    persisted: list[Action] = []
    for draft in metadata.actions:
        action = create_action(
            session,
            user_id=user_id,
            conversation_id=conversation_id,
            description=draft.description,
            source_type=SOURCE_TYPE,
            source_id=primary_id,
            action_type=draft.action_type,
            urgency=draft.urgency,
            deadline_date=draft.deadline_date,
        )
        persisted.append(action)

    logger.info(
        "extracted %d action(s) for document %s (document_type=%r, urgency=%s)",
        len(persisted),
        primary_id,
        metadata.document_type,
        metadata.urgency,
    )
    return persisted
