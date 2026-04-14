"""Database engine and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from market_agent.config import settings
from market_agent.memory.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)
    return _SessionLocal


def get_session() -> Session:
    """Return a new SQLAlchemy Session.  Caller is responsible for closing it."""
    factory = get_session_factory()
    return factory()


def init_db() -> None:
    """Create all tables (idempotent — safe to call on an existing DB)."""
    Base.metadata.create_all(bind=get_engine())
