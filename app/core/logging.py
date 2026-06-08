"""Structured application logging — layer 1 of the observability plan.

`structlog` renders our own events as contextvars-enriched, PII-redacted lines
on stdout (JSON in production, a human-readable console in development). Bind the
request context once per turn and every downstream line carries it:

    import structlog
    structlog.contextvars.bind_contextvars(conversation_id=..., user_id=...)

    from app.core.logging import get_logger
    log = get_logger(__name__)
    log.info("router_decision", node="document_helper_node")

This is deliberately a *standalone* structlog setup: it does not hijack the root
logger, so stdlib/uvicorn/apscheduler logs keep their current format (and the
launchd watchdog keeps detecting their `ERROR`/`Traceback` lines). Unifying every
log into one JSON stream — and teaching the watchdog to read it — is a follow-up.
LLM tracing (Langfuse) is layer 2, deferred to the DPIA.
"""

import logging

import structlog

# Values under these keys are letter/message content — never let them reach a sink.
_REDACT_KEYS = frozenset({"content_text", "body", "body_template", "extracted_text"})
_REDACTED = "[redacted]"


def _redact_pii(_logger: object, _method: str, event_dict: dict) -> dict:
    for key in _REDACT_KEYS:
        if event_dict.get(key) is not None:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_pii,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
