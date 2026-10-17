"""FastAPI application entry point for DB-Pulse."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.database import engine
from app.routes import alerts, history, locks, monitoring, partitions, slow_queries


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release the SQLAlchemy connection pool when the API shuts down."""
    yield
    if engine is not None:
        engine.dispose()


app = FastAPI(
    title="DB-Pulse",
    description="MySQL monitoring with explicit DB-Pulse history snapshots",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(monitoring.router)
app.include_router(locks.router)
app.include_router(slow_queries.router)
app.include_router(partitions.router)
app.include_router(history.router)
app.include_router(alerts.router)


@app.get("/")
def home() -> dict[str, str]:
    """Return a simple project welcome message."""
    return {"message": "Welcome to DB-Pulse", "status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    """Confirm that the application process can answer requests."""
    return {"status": "healthy", "project": "DB-Pulse"}
