import base64
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from app.models.document import Document


class DocumentExtractionService:
    def extract_text(self, document: Document) -> str | None:
        if not document.file_storage_path:
            return None

        path = Path(document.file_storage_path)
        if not path.exists():
            return None

        if document.mime_type == "application/pdf":
            return self._extract_pdf_text(path)

        if document.mime_type.startswith("image/"):
            return self._extract_image_text(path)

        return None

    def _extract_pdf_text(self, path: Path) -> str | None:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(page.strip() for page in pages if page.strip())
        return text or None

    def _extract_image_text(self, path: Path) -> str | None:
        model = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
        mime_type = _mime_type_from_suffix(path.suffix)
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "Read this document image and extract the visible text as faithfully as possible. Return only the extracted text.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
            ]
        )
        response = model.invoke([message])
        text = getattr(response, "content", None)
        if isinstance(text, str):
            return text.strip() or None
        return None


def _mime_type_from_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".png":
        return "image/png"
    return "application/octet-stream"
