from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_service import get_chat_model
from app.workflows.intake_router.schemas import IntakeReasoningResult
from app.workflows.intake_router.state import IntakeRouterState


LOW_INFORMATION_MESSAGES = {
    "hi",
    "hey",
    "hallo",
    "hello",
    "ok",
    "oke",
    "okay",
    "ja",
    "nee",
    "help",
}


def detect_message_kind(state: IntakeRouterState) -> IntakeRouterState:
    message_type = state.get("current_message_type", "unknown")
    message_text = (state.get("current_message_text") or "").strip()
    lowered_text = message_text.lower()

    if message_type in {"image", "document"}:
        candidate = "document_help"
    elif "digid" in lowered_text:
        candidate = "digid_help"
    else:
        candidate = "general_intake"

    inferred_language = _infer_language(message_text)
    is_low_information_message = _is_low_information_message(message_text)

    return {
        **state,
        "workflow_type_candidate": candidate,
        "inferred_language": inferred_language,
        "is_low_information_message": is_low_information_message,
    }


def decide_entry_path(state: IntakeRouterState) -> IntakeRouterState:
    has_active_workflow = state.get("has_active_workflow", False)
    active_workflow_type = state.get("active_workflow_type")
    workflow_type_candidate = state.get("workflow_type_candidate")

    if has_active_workflow and active_workflow_type:
        transition_to_workflow = active_workflow_type
        should_continue_existing_workflow = True
        should_start_new_workflow = False
    else:
        transition_to_workflow = workflow_type_candidate or "general_intake"
        should_continue_existing_workflow = False
        should_start_new_workflow = True

    if transition_to_workflow == "general_intake":
        missing_information = ["situation_summary"]
        intake_complete = False
    else:
        missing_information = []
        intake_complete = transition_to_workflow != "general_intake"

    return {
        **state,
        "should_continue_existing_workflow": should_continue_existing_workflow,
        "should_start_new_workflow": should_start_new_workflow,
        "transition_to_workflow": transition_to_workflow,
        "missing_information": missing_information,
        "intake_complete": intake_complete,
    }


def reason_about_intake(state: IntakeRouterState) -> IntakeRouterState:
    transition_to_workflow = state.get("transition_to_workflow") or "general_intake"

    if transition_to_workflow == "document_help":
        reply_text = _document_help_reply(state.get("display_name"), state.get("inferred_language") or state.get("preferred_language") or "nl")
        return {
            **state,
            "reply_text": reply_text,
            "next_expected_input": "document_processing",
            "open_loop": None,
        }

    if state.get("is_low_information_message") and state.get("open_loop"):
        return {
            **state,
            "reply_text": _soft_open_loop_reply(state),
        }

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(state)

    model = get_chat_model().with_structured_output(IntakeReasoningResult)
    result = model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )

    guided_journey_key = result.guided_journey_key or _derive_guided_journey_key(
        journey_candidate=result.journey_candidate,
        current_message_text=state.get("current_message_text"),
        situation_summary=result.situation_summary or state.get("situation_summary"),
        existing_workflow_type=state.get("active_workflow_type"),
    )

    return {
        **state,
        "situation_summary": result.situation_summary,
        "workflow_type_candidate": result.journey_candidate or state.get("workflow_type_candidate"),
        "guided_journey_key": guided_journey_key,
        "missing_information": result.missing_information,
        "intake_complete": result.intake_complete,
        "reply_text": result.reply_text,
        "next_expected_input": result.next_expected_input,
        "open_loop": result.open_loop,
        "transition_to_workflow": "guided_journey" if guided_journey_key else (result.journey_candidate or state.get("transition_to_workflow")),
    }


def _infer_language(text: str) -> str:
    lowered = text.lower()

    if _contains_cyrillic(text):
        return "uk"
    if any(token in lowered for token in ["hello", "help", "letter", "problem"]):
        return "en"
    return "nl"


def _contains_cyrillic(text: str) -> bool:
    return any("\u0400" <= char <= "\u04FF" for char in text)


def _is_low_information_message(text: str) -> bool:
    cleaned = text.strip().lower()
    return cleaned in LOW_INFORMATION_MESSAGES


def _soft_open_loop_reply(state: IntakeRouterState) -> str:
    language = state.get("inferred_language") or state.get("preferred_language") or "nl"
    open_loop = state.get("open_loop")

    if language == "en":
        if open_loop == "waiting_for_document_unclear_part":
            return "Hey, shall we keep going with that letter?"
        if open_loop == "waiting_for_digid_problem_description":
            return "Hey, where are you still getting stuck?"
        if open_loop == "waiting_for_document_upload":
            return "Hey, can you send me the document when you're ready?"
        return "Hey, how is it going?"

    if open_loop == "waiting_for_document_unclear_part":
        return "Hoi, zullen we verder kijken naar die brief?"
    if open_loop == "waiting_for_digid_problem_description":
        return "Hoi, waar loop je nu nog op vast?"
    if open_loop == "waiting_for_document_upload":
        return "Hoi, stuur het document maar door als je wilt."
    if open_loop == "waiting_for_user_situation":
        return "Hoi, vertel me even waar je nu hulp bij nodig hebt."
    return "Hoi, hoe staat het ermee?"


def _build_system_prompt() -> str:
    return (
        "You are Yara, a calm, practical, helpful WhatsApp guidance assistant for newcomers in The Hague. "
        "Your tone should feel like a supportive and sharp friend: warm, non-judgmental, direct, and brief. "
        "Always respond in the user's language when you can infer it. "
        "Do not write long blocks of text. Keep it conversational. Ask exactly one good next question. "
        "Your job here is to understand the user's situation, decide which journey fits best, identify what information is still missing, keep track of the current open loop, and write a short helpful reply. "
        "For general intake, focus first on understanding the user's situation and what they are currently running into. "
        "Use any existing situation summary as internal context, but do not repeat it back mechanically. "
        "Use any existing open loop as internal context for what is still pending in the conversation. "
        "Do not be generic if the message is still vague. Instead, guide the conversation toward concrete context. "
        "Do not use broad phrasing like 'What can I do for you?' if you can ask something more concrete. "
        "Do not mechanically repeat the user's words. Do not say phrases like 'You said that...' or 'You mention that...'. "
        "Do not greet the user in every message. Use their name sparingly and only when it feels natural. "
        "Write like a helpful human in chat, not like a formal assistant. "
        "Base your response only on the current message and the provided recent context. Do not invent details that are not supported. "
        "Do not infer DigiD or another specific journey unless it is clearly supported by the current message or recent context. "
        "If DigiD is clearly the topic, your job is to identify that handoff cleanly; do not try to run the full DigiD prerequisite flow inside general intake. "
        "Do not ask the same question again if the user has already partially answered it. Move the conversation forward. "
        "If the user sounds worried, afraid, or uncertain, briefly reassure them first and then ask one concrete next question. "
        "If this is a low-information follow-up and there is already context, continue gently from the existing context instead of restarting or becoming overly specific too quickly. "
        "If there is an open loop and the user sends a low-information follow-up, prefer a short soft continuation such as checking how it is going or where they are still stuck, instead of restating the full intake question. "
        "In that low-information + open-loop case, do not summarize the situation, do not infer new emotions unless the user explicitly expressed them in the current message, and do not repeat the original question in full. "
        "If the situation is still unclear, stay in general intake. "
        "Possible journey candidates are: general_intake, document_help, digid_help."
    )


def _build_user_prompt(state: IntakeRouterState) -> str:
    recent_messages = state.get("recent_messages", [])
    recent_lines = []
    for message in recent_messages:
        direction = message.get("direction", "unknown")
        content = message.get("content_text") or ""
        recent_lines.append(f"- {direction}: {content}")

    return (
        f"Display name: {state.get('display_name')}\n"
        f"Preferred language: {state.get('preferred_language')}\n"
        f"Inferred language: {state.get('inferred_language')}\n"
        f"Existing situation summary: {state.get('situation_summary')}\n"
        f"Existing open loop: {state.get('open_loop')}\n"
        f"Existing guided journey facts: {state.get('guided_journey_facts')}\n"
        f"Is low-information message: {state.get('is_low_information_message')}\n"
        f"Active workflow: {state.get('active_workflow_type')}\n"
        f"Active workflow step: {state.get('active_workflow_step')}\n"
        f"Current message type: {state.get('current_message_type')}\n"
        f"Current message text: {state.get('current_message_text')}\n"
        f"Suggested transition: {state.get('transition_to_workflow')}\n"
        f"Current missing information: {state.get('missing_information')}\n"
        f"Recent messages:\n" + "\n".join(recent_lines) + "\n\n"
        "If there is already a situation summary, refine or extend it naturally instead of starting from scratch. "
        "If a specific guided service journey is clearly the topic, prefer setting a guided_journey_key so a dedicated guided flow can take over, instead of keeping the conversation in broad intake longer than needed. "
        "The reply should continue the conversation naturally and should not expose internal state or summaries. "
        "If the current path is general_intake, the reply should gently move the user toward explaining their situation and what they are currently struggling with. "
        "Avoid generic assistant phrasing like 'How can I help you today?' unless the message already contains enough concrete context. "
        "When possible, ask a more concrete follow-up question instead of a broad one. "
        "Do not ask two questions in one message. Ask only the single most useful next question. "
        "If the user already gave new information, acknowledge that progress and build on it instead of looping. "
        "If the user expresses fear, worry, or uncertainty, briefly reassure them in a natural way before continuing. "
        "If this is a low-information follow-up and there is an open loop or a clear prior situation, prefer a short soft continuation like checking how things are going or where the user is still stuck. "
        "In that case, do not restate the full earlier question, do not summarize the situation back, and do not add reassurance or emotional interpretation unless the current message itself shows stress or worry. "
        "Choose an explicit open_loop when something is still pending. Use only one of: waiting_for_user_situation, waiting_for_document_type, waiting_for_document_unclear_part, waiting_for_document_upload, waiting_for_digid_problem_description. "
         "If a guided journey handoff is appropriate, set guided_journey_key. For example, use digid_help when DigiD is clearly the topic. "
        "If nothing is pending, set open_loop to null. "
        "For example, if the user mentions DigiD, ask what part they are stuck on. If they mention a document, ask what kind of document it is or what is unclear. "
        "The allowed values for next_expected_input are only: user_situation, document_upload, digid_problem_description, document_processing. "
        "The allowed values for missing_information are only: situation_summary, document_type, document_unclear_part, document_upload, digid_problem_description, language_confirmation. "
        "Use only those labels, never free text, for missing_information. "
        "Return a structured response with: situation_summary, journey_candidate, guided_journey_key, missing_information, intake_complete, reply_text, next_expected_input, open_loop."
    )


def _derive_guided_journey_key(
    *,
    journey_candidate: str | None,
    current_message_text: str | None,
    situation_summary: str | None,
    existing_workflow_type: str | None,
) -> str | None:
    combined = " ".join(part for part in [current_message_text or "", situation_summary or ""] if part).lower()

    if existing_workflow_type == "guided_journey":
        return None

    if journey_candidate == "digid_help" or "digid" in combined:
        return "digid_help"

    return None


def _document_help_reply(display_name: str | None, language: str) -> str:
    if language == "en":
        if display_name:
            return f"Hi {display_name}, I received your document. I’ll help you understand what it says and what the next step is."
        return "Hi, I received your document. I’ll help you understand what it says and what the next step is."

    if display_name:
        return f"Hoi {display_name}, ik heb je document ontvangen. Ik help je begrijpen wat erin staat en wat de volgende stap is."
    return "Hoi, ik heb je document ontvangen. Ik help je begrijpen wat erin staat en wat de volgende stap is."
