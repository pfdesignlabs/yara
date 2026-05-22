from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.message import Message
from app.services.document_understanding_schema import DocumentUnderstandingResult


def create_document_from_message(
    session: Session,
    *,
    user_id: str,
    conversation_id: str,
    source_message: Message,
    file_storage_path: str | None = None,
    file_name: str | None = None,
) -> Document:
    document = Document(
        user_id=user_id,
        conversation_id=conversation_id,
        source_message_id=source_message.id,
        file_storage_path=file_storage_path,
        mime_type=source_message.media_mime_type or "application/octet-stream",
        file_name=file_name,
        processing_status="received",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def update_document_storage_path(
    session: Session,
    document: Document,
    *,
    file_storage_path: str,
    processing_status: str | None = None,
) -> Document:
    document.file_storage_path = file_storage_path
    if processing_status is not None:
        document.processing_status = processing_status
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def update_document_extracted_text(
    session: Session,
    document: Document,
    *,
    extracted_text: str | None,
    processing_status: str | None = None,
) -> Document:
    document.extracted_text = extracted_text
    if processing_status is not None:
        document.processing_status = processing_status
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def update_document_understanding(
    session: Session,
    document: Document,
    *,
    result: DocumentUnderstandingResult,
    processing_status: str | None = None,
) -> Document:
    document.document_type = result.document_type
    document.journey_candidate = result.journey_candidate
    document.summary = result.summary
    document.suggested_next_step = result.suggested_next_step
    if processing_status is not None:
        document.processing_status = processing_status
    session.add(document)
    session.commit()
    session.refresh(document)
    return document
