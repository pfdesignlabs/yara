"""APScheduler boot — single in-app BackgroundScheduler with a DB jobstore.

One interval job (`reminder_dispatcher`) ticks every minute and sends due
reminders. Jobs are persisted in Postgres so a restart does not lose
schedule state.
"""

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.scheduler.reminder_dispatcher import dispatch_due_reminders_job

logger = logging.getLogger(__name__)

REMINDER_JOB_ID = "reminder_dispatcher"
REMINDER_INTERVAL_MINUTES = 1

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """Boot the BackgroundScheduler and register the reminder job."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    jobstore = SQLAlchemyJobStore(url=settings.database_url)
    scheduler = BackgroundScheduler(jobstores={"default": jobstore})
    scheduler.add_job(
        dispatch_due_reminders_job,
        trigger="interval",
        minutes=REMINDER_INTERVAL_MINUTES,
        id=REMINDER_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "APScheduler started — %s ticks every %s min",
        REMINDER_JOB_ID,
        REMINDER_INTERVAL_MINUTES,
    )
    return scheduler


def stop_scheduler() -> None:
    """Shut down the scheduler on app shutdown."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("APScheduler stopped")
