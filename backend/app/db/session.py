"""
SQLAlchemy engine and session factory.
Engine is created lazily so tests can override DATABASE_URL via env vars
before importing the models.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Lazy engine: created on first access so env vars in conftest.py apply
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        if url.startswith("postgresql+psycopg://") or url.startswith("postgresql://"):
            try:
                import psycopg  # noqa: F401
            except ImportError:
                # Fall back to psycopg2
                url = url.replace("postgresql+psycopg://", "postgresql+psycopg2://")
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

        try:
            temp_eng = create_engine(url, pool_pre_ping=True, future=True)
            with temp_eng.connect() as conn:
                conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            _engine = temp_eng
        except Exception:
            # When PostgreSQL is unreachable (e.g. running locally without Docker container),
            # fall back gracefully to local SQLite so the system functions end-to-end
            import os
            db_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sqlite_path = os.path.join(db_dir, "storage", "doc_intel.db").replace("\\", "/")
            os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
            _engine = create_engine(f"sqlite:///{sqlite_path}", pool_pre_ping=True, future=True)

    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


# Module-level proxy properties
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)
    def begin(self):
        return _get_engine().begin()
    def connect(self):
        return _get_engine().connect()


engine = _EngineProxy()


class SessionLocal:
    """Callable proxy that returns a session."""
    def __new__(cls):
        return _get_session_local()()


def get_db():
    db = _get_session_local()()
    try:
        yield db
    finally:
        db.close()
