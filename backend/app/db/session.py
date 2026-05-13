from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# SQLite needs check_same_thread=False; PostgreSQL uses pool_pre_ping.
_connect_args: dict = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(
    settings.database_url,
    pool_pre_ping=not _is_sqlite,
    connect_args=_connect_args,
)

# Enable WAL mode and foreign keys for SQLite connections
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy session.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

