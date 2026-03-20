"""Database configuration for Product Matrix API.

Reuses the existing sku_database connection pattern.
Creates two SQLAlchemy engines: one for public schema, one for hub schema.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load .env from project root
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env", override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _connection_string() -> str:
    host = _env("POSTGRES_HOST", _env("SUPABASE_HOST", "localhost"))
    port = _env("POSTGRES_PORT", _env("SUPABASE_PORT", "5432"))
    db = _env("POSTGRES_DB", _env("SUPABASE_DB", "postgres"))
    user = _env("POSTGRES_USER", _env("SUPABASE_USER", "postgres"))
    pwd = _env("POSTGRES_PASSWORD", _env("SUPABASE_PASSWORD", ""))
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


_conn_str = _connection_string()
_is_supabase = "supabase" in _conn_str.lower() or "pooler" in _conn_str.lower()
_connect_args = {"sslmode": "require"} if _is_supabase else {}

engine = create_engine(
    _conn_str,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency — yields a DB session, auto-closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
