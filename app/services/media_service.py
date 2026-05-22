from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.models.document import Document

settings = get_settings()


def download_media_for_document(document: Document, media_url: str) -> str:
    suffix = _guess_extension(media_url, document.mime_type)
    target_dir = Path(settings.uploads_dir) / document.user_id / document.id
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / f"original{suffix}"

    with httpx.Client(
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        response = client.get(media_url)
        response.raise_for_status()
        target_path.write_bytes(response.content)

    return str(target_path)


def _guess_extension(media_url: str, mime_type: str | None) -> str:
    if mime_type == "application/pdf":
        return ".pdf"
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/png":
        return ".png"

    parsed = urlparse(media_url)
    suffix = Path(parsed.path).suffix
    return suffix or ".bin"
