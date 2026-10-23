"""Database engine and session management."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

if settings.database_url.startswith("sqlite:///") and not settings.database_url.startswith("sqlite:////"):
    database_file = settings.database_url.removeprefix("sqlite:///").split("?", 1)[0]
    if database_file and database_file != ":memory:":
        Path(database_file).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    from . import models  # noqa: F401
    from .domain import models as domain_models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
