from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.knowledge_service import SelectedKnowledge, format_selected_knowledge
from app.services.llm_service import get_chat_model


class DigiDReplyService:
    def build_reply(
        self,
        *,
        user_message: str | None,
        language: str,
        workflow_type: str | None,
        workflow_step: str | None,
        situation_summary: str | None = None,
        open_loop: str | None = None,
        missing_information: list[str] | None = None,
        document_summary: str | None = None,
        document_type: str | None = None,
        document_suggested_next_step: str | None = None,
        selected_knowledge: SelectedKnowledge | None = None,
    ) -> str | None:
        if not selected_knowledge or not selected_knowledge.get("chunks"):
            return None

        model = get_chat_model()
        result = model.invoke(
            [
                SystemMessage(content=self._system_prompt(language)),
                HumanMessage(
                    content=self._user_prompt(
                        user_message=user_message,
                        language=language,
                        workflow_type=workflow_type,
                        workflow_step=workflow_step,
                        situation_summary=situation_summary,
                        open_loop=open_loop,
                        missing_information=missing_information,
                        document_summary=document_summary,
                        document_type=document_type,
                        document_suggested_next_step=document_suggested_next_step,
                        selected_knowledge=selected_knowledge,
                    )
                ),
            ]
        )

        content = result.content if hasattr(result, "content") else str(result)
        return content.strip() if content else None

    def _system_prompt(self, language: str) -> str:
        if language == "en":
            return (
                "You are Yara, a calm, practical WhatsApp guidance assistant. "
                "Write a short, grounded reply for someone who needs help with DigiD. "
                "Use the provided trusted knowledge when relevant, but do not dump or quote it mechanically. "
                "Be concrete about the next useful step. "
                "If prerequisites matter, mention only the ones relevant now. "
                "If the user seems stuck, reduce confusion and point to one next step. "
                "You must reply fully in the specified language. "
                "Treat the provided situation summary, missing information, and open loop as true current state. "
                "Do not ask again about facts that are already known from that state. "
                "If it is already known that the user has no BSN, no fixed address, or no mailing address, do not ask those again. Move forward from that point. "
                "If you ask a follow-up question, make it specific to the next fork in the process, not generic. "
                "Keep it short, human, and non-bureaucratic. "
                "Do not invent facts beyond the provided context. "
                "Do not ask more than one question."
            )

        return (
            "Je bent Yara, een rustige en praktische WhatsApp-assistent. "
            "Schrijf een kort, goed onderbouwd antwoord voor iemand die hulp nodig heeft met DigiD. "
            "Gebruik de meegegeven betrouwbare kennis als die relevant is, maar plak die niet letterlijk of mechanisch terug. "
            "Wees concreet over de eerstvolgende nuttige stap. "
            "Als prerequisites belangrijk zijn, noem alleen wat nu relevant is. "
            "Als iemand vastloopt, verminder dan verwarring en stuur op één volgende stap. "
            "Je moet volledig antwoorden in de opgegeven taal. "
            "Behandel de meegegeven situation summary, missing information en open loop als de echte huidige stand van zaken. "
            "Vraag niet opnieuw naar feiten die daarin al bekend zijn. "
            "Als al bekend is dat de gebruiker geen BSN, geen vast adres of geen briefadres heeft, vraag daar dan niet opnieuw naar. Ga verder vanaf dat punt. "
            "Als je een vervolgvraag stelt, maak die dan specifiek voor de volgende splitsing in het proces, niet generiek. "
            "Houd het kort, menselijk en niet-bureaucratisch. "
            "Verzin geen feiten buiten de gegeven context. "
            "Stel niet meer dan één vraag."
        )

    def _user_prompt(
        self,
        *,
        user_message: str | None,
        language: str,
        workflow_type: str | None,
        workflow_step: str | None,
        situation_summary: str | None,
        open_loop: str | None,
        missing_information: list[str] | None,
        document_summary: str | None,
        document_type: str | None,
        document_suggested_next_step: str | None,
        selected_knowledge: SelectedKnowledge,
    ) -> str:
        return (
            f"Language: {language}\n"
            f"Workflow type: {workflow_type}\n"
            f"Workflow step: {workflow_step}\n"
            f"Situation summary: {situation_summary}\n"
            f"Open loop: {open_loop}\n"
            f"Missing information: {missing_information}\n"
            f"User message: {user_message}\n"
            f"Document type: {document_type}\n"
            f"Document summary: {document_summary}\n"
            f"Document suggested next step: {document_suggested_next_step}\n\n"
            f"{format_selected_knowledge(selected_knowledge)}\n\n"
            "Write the best next WhatsApp reply now."
        )
