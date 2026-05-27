import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.scheduler.cron import start_scheduler, stop_scheduler

_REQUIRED_SECRETS = (
    "openai_api_key",
    "twilio_account_sid",
    "twilio_auth_token",
    "twilio_whatsapp_number",
)


def _assert_secrets_present(settings: Settings) -> None:
    missing = [name for name in _REQUIRED_SECRETS if not getattr(settings, name)]
    if missing:
        raise RuntimeError(
            f"APP_ENV={settings.app_env} requires non-empty secrets, missing: {', '.join(missing)}"
        )


settings = get_settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)
logger.info("Yara starting in %s environment", settings.app_env)

_is_dev = settings.app_env == "development"

if not _is_dev:
    _assert_secrets_present(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Yara API",
    version="0.1.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
    lifespan=lifespan,
)
app.include_router(router)
