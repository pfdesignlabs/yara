from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.guided_journey_service import GuidedJourneyService
from app.services.knowledge_service import KnowledgeService, format_selected_knowledge
from app.services.llm_service import get_chat_model
from app.workflows.guided_journey.schemas import GuidedJourneyFactExtractionResult
from app.workflows.guided_journey.state import GuidedJourneyState


def extract_facts(state: GuidedJourneyState) -> GuidedJourneyState:
    model = get_chat_model().with_structured_output(GuidedJourneyFactExtractionResult)
    result = model.invoke(
        [
            SystemMessage(content=_fact_extraction_system_prompt(state["journey_key"])),
            HumanMessage(content=_fact_extraction_user_prompt(state)),
        ]
    )

    merged = _merge_facts(state, result)
    return {
        **state,
        "facts": merged,
    }


def decide_route(state: GuidedJourneyState) -> GuidedJourneyState:
    facts = state.get("facts", {})
    blockers = _derive_blockers(facts, state["journey_key"])
    recommended_route = GuidedJourneyService().decide_route(
        journey_key=state["journey_key"],
        facts=facts,
    )

    return {
        **state,
        "blockers": blockers,
        "recommended_route": recommended_route,
    }


def plan_next_step(state: GuidedJourneyState) -> GuidedJourneyState:
    next_question_key = None
    if state.get("recommended_route") == "collect_more_context":
        next_question_key = GuidedJourneyService().next_question_key(
            journey_key=state["journey_key"],
            facts=state.get("facts", {}),
        )

    return {
        **state,
        "next_question_key": next_question_key,
    }


def render_reply(state: GuidedJourneyState) -> GuidedJourneyState:
    language = state.get("inferred_language") or state.get("preferred_language") or "nl"
    selected_knowledge = _select_knowledge(state)

    reply_text = _deterministic_reply(state, language)
    if reply_text is None:
        model = get_chat_model()
        result = model.invoke(
            [
                SystemMessage(content=_render_system_prompt(language)),
                HumanMessage(content=_render_user_prompt(state, selected_knowledge)),
            ]
        )
        content = result.content if hasattr(result, "content") else str(result)
        reply_text = content.strip() if content else None

    return {
        **state,
        "reply_text": reply_text,
    }


def _select_knowledge(state: GuidedJourneyState) -> dict:
    return KnowledgeService().select_for_journey(
        journey_key=state["journey_key"],
        user_message=state.get("current_message_text"),
    )


def _merge_facts(state: GuidedJourneyState, result: GuidedJourneyFactExtractionResult) -> dict:
    merged = dict(state.get("facts", {}))
    payload = result.model_dump().get("values", {})
    for key, value in payload.items():
        if value is not None:
            merged[key] = value
    return merged


def _derive_blockers(facts: dict[str, object], journey_key: str) -> list[str]:
    blockers: list[str] = []
    for fact_def in GuidedJourneyService().fact_definitions(journey_key=journey_key):
        blocker_key = fact_def.get("blocker_key")
        if blocker_key and facts.get(fact_def["key"]) is False:
            blockers.append(blocker_key)
    return blockers


def _deterministic_reply(state: GuidedJourneyState, language: str) -> str | None:
    service = GuidedJourneyService()
    route = state.get("recommended_route")
    next_question_key = state.get("next_question_key")

    if route and route != "collect_more_context":
        return service.render_template(
            journey_key=state["journey_key"],
            template_group="routes",
            template_key=route,
            language=language,
        )

    if next_question_key:
        return service.render_template(
            journey_key=state["journey_key"],
            template_group="questions",
            template_key=next_question_key,
            language=language,
        )

    return None


def _fact_extraction_system_prompt(journey_key: str) -> str:
    return (
        f"You extract structured prerequisite facts for the guided journey '{journey_key}' from a WhatsApp conversation. "
        "Only set fields when clearly supported by the current message or recent conversation context. "
        "Do not guess. Leave unknown fields null. "
        "Return them under the 'values' object, keyed exactly by fact key."
    )


def _fact_extraction_user_prompt(state: GuidedJourneyState) -> str:
    recent_lines = []
    for message in state.get("recent_messages", []):
        recent_lines.append(f"- {message.get('direction')}: {message.get('content_text') or ''}")

    fact_lines = []
    for fact_def in GuidedJourneyService().fact_definitions(journey_key=state["journey_key"]):
        fact_lines.append(
            f"- key={fact_def['key']}; type={fact_def.get('type')}; label={fact_def.get('label')}; hint={fact_def.get('extraction_hint')}"
        )

    return (
        f"Journey key: {state.get('journey_key')}\n"
        "Fact definitions:\n" + "\n".join(fact_lines) + "\n"
        f"Current message: {state.get('current_message_text')}\n"
        f"Existing facts: {state.get('facts', {})}\n"
        f"Recent messages:\n" + "\n".join(recent_lines)
    )


def _render_system_prompt(language: str) -> str:
    if language == "uk":
        return (
            "Ти Yara, спокійний і практичний WhatsApp-помічник. "
            "Сформулюй коротку, людяну, конкретну відповідь українською. "
            "Не став більше одного запитання. "
            "Не повертайся до загального intake, якщо вже відомий наступний крок."
        )
    if language == "en":
        return (
            "You are Yara, a calm and practical WhatsApp assistant. "
            "Write a short, human, concrete reply in English. "
            "Do not ask more than one question. "
            "Do not fall back to generic intake if the next step is already known."
        )
    return (
        "Je bent Yara, een rustige en praktische WhatsApp-assistent. "
        "Schrijf een kort, menselijk en concreet antwoord in de juiste taal. "
        "Stel niet meer dan één vraag. "
        "Val niet terug op generieke intake als de volgende stap al duidelijk is."
    )


def _render_user_prompt(state: GuidedJourneyState, selected_knowledge: dict) -> str:
    return (
        f"Journey key: {state.get('journey_key')}\n"
        f"Language: {state.get('inferred_language') or state.get('preferred_language') or 'nl'}\n"
        f"Situation summary: {state.get('situation_summary')}\n"
        f"Current message: {state.get('current_message_text')}\n"
        f"Known facts: {state.get('facts', {})}\n"
        f"Blockers: {state.get('blockers')}\n"
        f"Recommended route: {state.get('recommended_route')}\n"
        f"Next question key: {state.get('next_question_key')}\n\n"
        f"{format_selected_knowledge(selected_knowledge)}\n\n"
        "Write the best next WhatsApp reply now."
    )
