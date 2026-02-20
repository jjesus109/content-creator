import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.scheduler.setup import create_scheduler
from app.scheduler.registry import register_jobs
from app.routes.health import router as health_router

# Configure structured logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan — startup before yield, shutdown after yield.
    Scheduler starts here so it is alive before the first request.
    """
    # Startup
    logger.info("Starting up content-creation service.")
    scheduler = create_scheduler()
    register_jobs(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("APScheduler started with %d jobs.", len(scheduler.get_jobs()))

    yield  # App is running

    # Shutdown
    logger.info("Shutting down — stopping scheduler.")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Content Creation Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
