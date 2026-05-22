from langchain_core.messages import HumanMessage, SystemMessage

from app.models.document import Document
from app.services.document_understanding_schema import DocumentUnderstandingResult
from app.services.llm_service import get_chat_model


class DocumentUnderstandingService:
    def understand(self, document: Document, language: str | None = None) -> DocumentUnderstandingResult | None:
        if not document.extracted_text:
            return None

        model = get_chat_model().with_structured_output(DocumentUnderstandingResult)
        result = model.invoke(
            [
                SystemMessage(content=self._system_prompt()),
                HumanMessage(content=self._user_prompt(document.extracted_text, language=language)),
            ]
        )
        return result

    def _system_prompt(self) -> str:
        return (
            "You are helping interpret official and practical documents for newcomers in the Netherlands. "
            "Your job is to identify what kind of document this is, give a short practical summary, suggest the most likely client journey, and suggest the next helpful step. "
            "Be careful, practical, and concise. Do not invent details that are not supported by the text. "
            "Return user-facing fields in the user's language when a target language is provided. "
            "Possible journey candidates include: general_intake, document_help, digid_help."
        )

    def _user_prompt(self, extracted_text: str, language: str | None = None) -> str:
        language_instruction = (
            f"The user's language is: {language}. Return document_type, summary, and suggested_next_step in that language. "
            if language
            else ""
        )
        return (
            "Read the extracted text below and return a structured understanding of the document.\n\n"
            f"{language_instruction}"
            "Keep the summary and suggested next step short, practical, and easy to understand.\n\n"
            f"Extracted text:\n{extracted_text}"
        )
