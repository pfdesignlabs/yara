from app.models.document import Document
from app.services.knowledge_service import SelectedKnowledge


def build_inbound_ack_reply(display_name: str | None = None) -> str:
    if display_name:
        return f"Hoi {display_name}, ik heb je bericht goed ontvangen."
    return "Hoi, ik heb je bericht goed ontvangen."


def build_document_understanding_reply(
    document: Document,
    language: str | None = None,
    selected_knowledge: SelectedKnowledge | None = None,
) -> str | None:
    if not document.summary:
        return None

    language = language or "nl"

    if language == "en":
        return _build_document_understanding_reply_en(document, selected_knowledge=selected_knowledge)
    return _build_document_understanding_reply_nl(document, selected_knowledge=selected_knowledge)



def _build_document_understanding_reply_nl(
    document: Document,
    selected_knowledge: SelectedKnowledge | None = None,
) -> str:
    parts: list[str] = []

    if document.document_type:
        parts.append(f"Dit lijkt { _lowercase_first(document.document_type.strip()) }.")
    else:
        parts.append(_compact_sentence(document.summary))

    if document.suggested_next_step:
        parts.append(f"De belangrijkste stap is: {_clean_sentence(document.suggested_next_step)}")

    practical_hint = _best_practical_hint(selected_knowledge, language="nl")
    if practical_hint:
        parts.append(practical_hint)

    parts.append("Als je wilt, help ik je hier stap voor stap mee.")
    return "\n\n".join(parts)



def _build_document_understanding_reply_en(
    document: Document,
    selected_knowledge: SelectedKnowledge | None = None,
) -> str:
    parts: list[str] = []

    if document.document_type:
        parts.append(f"This looks like { _lowercase_first(document.document_type.strip()) }.")
    else:
        parts.append(_compact_sentence(document.summary))

    if document.suggested_next_step:
        parts.append(f"The most important next step is: {_clean_sentence(document.suggested_next_step)}")

    practical_hint = _best_practical_hint(selected_knowledge, language="en")
    if practical_hint:
        parts.append(practical_hint)

    parts.append("If you want, I can help you with this step by step.")
    return "\n\n".join(parts)



def _lowercase_first(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:]



def _clean_sentence(text: str) -> str:
    return text.strip().rstrip()



def _compact_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text


def _best_practical_hint(selected_knowledge: SelectedKnowledge | None, language: str = "nl") -> str | None:
    if not selected_knowledge or not selected_knowledge.get("chunks"):
        return None

    for chunk in selected_knowledge["chunks"]:
        hint = _extract_first_practical_sentence(chunk.get("chunk_text") or "")
        if hint:
            if language == "en":
                return f"Relevant here: {hint}"
            return f"Wat hierbij helpt: {hint}"

    return None


def _extract_first_practical_sentence(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("["):
            continue
        if stripped.startswith("*") or stripped.startswith("-"):
            stripped = stripped.lstrip("*- ").strip()
        if len(stripped) < 20:
            continue
        return stripped.rstrip()

    return None
