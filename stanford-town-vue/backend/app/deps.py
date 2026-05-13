"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from config.settings import Settings, get_settings as _get_settings
from runner.manager import SimulationManager, manager_singleton
from storage.db import SessionLocal


def get_settings() -> Settings:
    """Cached Settings dependency."""
    return _get_settings()


def get_db() -> Iterator[Session]:
    """Yield a SQLAlchemy session scoped to a single request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_manager() -> SimulationManager:
    """Return the SimulationManager singleton.

    During Wave 1 this is a stub manager; M3 replaces the singleton with the
    real instance backed by worker threads.
    """
    return manager_singleton
