import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.db.migrations import run_migrations
from app.scheduler.setup import create_scheduler
from app.scheduler.registry import register_jobs
from app.routes.health import router as health_router
from app.routes.webhooks import router as webhooks_router
from app.telegram.app import build_telegram_app, start_telegram_polling, stop_telegram_polling
from app.services.telegram import set_fastapi_app

# Configure structured logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan — startup before yield, shutdown after yield.
    Scheduler starts here so it is alive before the first request.
    """
    logger.info("Starting up content-creation service.")
    run_migrations()

    scheduler = create_scheduler()
    register_jobs(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("APScheduler started with %d jobs.", len(scheduler.get_jobs()))

    tg_app = build_telegram_app()
    await start_telegram_polling(tg_app)
    app.state.telegram_app = tg_app
    set_fastapi_app(app)  # allows APScheduler threads to reach app.state.telegram_app
    logger.info("Telegram Application started.")

    yield  # App is running

    logger.info("Shutting down.")
    await stop_telegram_polling(tg_app)
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Content Creation Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(webhooks_router)
