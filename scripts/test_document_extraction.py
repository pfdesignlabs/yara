from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document
from app.services.document_extraction_service import DocumentExtractionService


def main() -> None:
    session = SessionLocal()
    try:
        statement = select(Document).order_by(Document.created_at.desc()).limit(1)
        document = session.scalars(statement).first()
        if document is None:
            print("No document found")
            return

        print(f"Testing document: {document.id}")
        print(f"Mime type: {document.mime_type}")
        print(f"Path: {document.file_storage_path}")

        text = DocumentExtractionService().extract_text(document)
        print("--- Extracted text ---")
        print(text or "<no text>")
    finally:
        session.close()


if __name__ == "__main__":
    main()
