"""LLM-facing tool that builds a tappable `mailto:` URL."""

from urllib.parse import quote

from langchain_core.tools import tool


@tool
def draft_mail(to_email: str, subject: str, body: str) -> str:
    """Build a `mailto:` URL the user can tap from WhatsApp to open their mail
    client with the message pre-filled.

    Use this when the user has decided to send an email (e.g. an objection
    letter, a request for information) and you have drafted the body and
    subject together. The returned URL is what we send back to WhatsApp.

    Language rules for `subject` and `body`:
    - If the user is already chatting in Dutch, write the email in Dutch
      only.
    - Otherwise, write it bilingual: first the user's own language, then a
      separator line `---`, then the Dutch translation. The Dutch version
      is what the recipient (gemeente, woningcorporatie, advocaat, ...)
      actually reads; the user-language version lets the user understand
      and verify what they are sending.

    Bilingual body layout:

        <message in the user's language>

        ---

        <same message in Dutch>

    For a bilingual subject: combine both, e.g. "Objection / Bezwaar".

    Args:
        to_email: recipient address (e.g. "gemeente@denhaag.nl"). Must
            contain "@".
        subject: subject line as plain text — do not URL-encode yourself.
        body: full message body as plain text. Newlines are preserved and
            percent-encoded so the mail client renders them correctly.
    """
    if "@" not in to_email:
        raise ValueError(f"to_email must contain '@', got {to_email!r}")
    subject_enc = quote(subject, safe="")
    body_enc = quote(body, safe="")
    return f"mailto:{to_email}?subject={subject_enc}&body={body_enc}"
