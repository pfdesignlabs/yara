"""LLM-facing tool that builds a tappable `mailto:` URL behind a TinyURL."""

import logging
import time
from urllib.parse import quote

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_TINYURL_CREATE = "https://tinyurl.com/api-create.php"
_TINYURL_TIMEOUT_S = 20.0
_TINYURL_MAX_ATTEMPTS = 3

# Process-level memoisation: when gpt-5.5 emits two `draft_mail` calls with
# the same payload in a single turn (observed live), the second one would
# otherwise hit TinyURL again and possibly time out. Return the cached
# short URL instead. Bounded growth is fine for our prototype scale.
_SHORT_URL_CACHE: dict[str, str] = {}

# AI-disclosure footer always appended to the body so the recipient knows
# the message was drafted with assistance. Kept in Dutch since the
# recipient is a Dutch institution; the user has already seen the body in
# their own language in chat.
_AI_DISCLOSURE_NL = (
    "— Dit bericht is opgesteld met hulp van Yara, een digitale assistent "
    "voor nieuwkomers in Den Haag."
)


@tool
def draft_mail(to_email: str, subject: str, body: str) -> str:
    """Build a `mailto:` URL the user can tap from WhatsApp to open their mail
    client with the message pre-filled.

    The full `mailto:` URL is shortened via TinyURL so it always fits in a
    single WhatsApp message (Twilio's 1600-char limit otherwise blocks any
    bilingual mailto with Cyrillic / Arabic body, where each non-ASCII char
    becomes a 3-byte percent-encoded sequence). Tapping the TinyURL
    301-redirects to the original mailto, opening the user's mail client
    with the body pre-filled.

    Use this when the user has decided to send an email (e.g. an objection
    letter, a request for information) and you have drafted the body and
    subject together.

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
    body_with_disclosure = f"{body.rstrip()}\n\n{_AI_DISCLOSURE_NL}"
    subject_enc = quote(subject, safe="")
    body_enc = quote(body_with_disclosure, safe="")
    mailto_url = f"mailto:{to_email}?subject={subject_enc}&body={body_enc}"

    cached = _SHORT_URL_CACHE.get(mailto_url)
    if cached is not None:
        logger.info("tinyurl cache hit (short=%s)", cached)
        return cached

    last_exc: Exception | None = None
    for attempt in range(1, _TINYURL_MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(
                _TINYURL_CREATE,
                params={"url": mailto_url},
                timeout=_TINYURL_TIMEOUT_S,
            )
            response.raise_for_status()
            short_url = response.text.strip()
            if not short_url.startswith("https://tinyurl.com/"):
                raise ValueError(f"TinyURL returned unexpected response: {short_url!r}")
            _SHORT_URL_CACHE[mailto_url] = short_url
            logger.info(
                "tinyurl created (mailto len=%d, short=%s, attempt=%d)",
                len(mailto_url),
                short_url,
                attempt,
            )
            return short_url
        except httpx.TimeoutException as e:
            last_exc = e
            logger.warning("tinyurl timeout on attempt %d/%d", attempt, _TINYURL_MAX_ATTEMPTS)
            if attempt < _TINYURL_MAX_ATTEMPTS:
                time.sleep(attempt)  # 1s, 2s backoff

    assert last_exc is not None
    raise last_exc
