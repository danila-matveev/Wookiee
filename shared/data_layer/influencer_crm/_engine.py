"""SQLAlchemy engine + scoped session for the Influencer CRM API.

One module-level engine, sessions per request. Pool size kept small (5)
because the Supabase pooler already pools — we don't need a deep client-side pool.

Note: search_path is set via a 'connect' event listener rather than the DSN
options parameter. Supabase's pgbouncer strips the options query parameter,
so SET search_path in the post-connect hook is the only reliable approach.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from services.influencer_crm.config import DB_DSN

_engine: Engine = create_engine(
    DB_DSN,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(_engine, "connect")
def _set_search_path(dbapi_conn, connection_record) -> None:
    """Set search_path on every new physical connection.

    pgbouncer strips the options DSN parameter, so this hook is the only
    reliable way to ensure unqualified table names resolve to the crm schema.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO crm, public")
    cursor.close()


_Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


@contextmanager
def session_factory() -> Iterator[Session]:
    """Yield a Session, commit on clean exit, rollback on exception."""
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    """Test hook — exposed only so tests can dispose between modules."""
    return _engine
