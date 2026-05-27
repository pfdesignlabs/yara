"""Inbound attachments: download from Twilio, persist as Document, extract text."""

import logging
import mimetypes
from pathlib import Path

import httpx
from pypdf import PdfReader
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document

logger = logging.getLogger(__name__)

UPLOADS_BASE = Path("/app/storage/uploads")
_DOWNLOAD_TIMEOUT_SECONDS = 30.0

_EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_settings = get_settings()


def download_twilio_media(
    *,
    media_url: str,
    mime_type: str,
    user_id: str,
    external_message_id: str,
) -> Path:
    """Fetch a Twilio media URL with Basic Auth and write it to disk.

    Saved at `storage/uploads/<user_id>/<external_message_id><ext>`.
    """
    auth = (_settings.twilio_account_sid, _settings.twilio_auth_token)
    ext = _EXTENSION_BY_MIME.get(mime_type) or mimetypes.guess_extension(mime_type) or ".bin"
    user_dir = UPLOADS_BASE / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / f"{external_message_id}{ext}"

    with httpx.Client(
        auth=auth, follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS
    ) as client:
        response = client.get(media_url)
        response.raise_for_status()
        target.write_bytes(response.content)

    logger.info(
        "Downloaded Twilio media: %s → %s (%d bytes)",
        media_url,
        target,
        len(response.content),
    )
    return target


def create_document(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    source_message_id: str,
    file_storage_path: Path,
    mime_type: str,
    file_name: str | None = None,
) -> Document:
    """Create a `documents` row, extracting PDF text on the way in."""
    extracted = _extract_pdf_text(file_storage_path) if mime_type == "application/pdf" else None
    document = Document(
        user_id=user_id,
        conversation_id=conversation_id,
        source_message_id=source_message_id,
        file_storage_path=str(file_storage_path),
        mime_type=mime_type,
        file_name=file_name,
        extracted_text=extracted,
        processing_status="processed" if extracted is not None else "received",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def _extract_pdf_text(path: Path) -> str | None:
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        return text or None
    except Exception:
        logger.exception("Failed to extract text from PDF %s", path)
        return None


_MAX_DOC_HELPER_DOCS = 10


def get_recent_documents_for_doc_helper(session: Session, conversation_id: str) -> list[Document]:
    """Return the document(s) the doc_helper should see, in chronological order.

    - If the most recent upload is a PDF, return just that PDF (list of one).
    - Otherwise collect the run of consecutive image uploads at the head of the
      history (newest-first scan) and return them oldest-first so the LLM sees
      pages in upload order. Capped at `_MAX_DOC_HELPER_DOCS`.
    """
    statement = (
        select(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(desc(Document.created_at))
        .limit(_MAX_DOC_HELPER_DOCS)
    )
    docs = list(session.scalars(statement).all())
    if not docs:
        return []
    if docs[0].mime_type == "application/pdf":
        return [docs[0]]
    batch: list[Document] = []
    for doc in docs:
        if not doc.mime_type.startswith("image/"):
            break
        batch.append(doc)
    return list(reversed(batch))
