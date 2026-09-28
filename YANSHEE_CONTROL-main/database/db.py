"""
SQLite database initialisation using SQLAlchemy.
"""
import os
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from logs.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def init_db(db_path: str):
    """Create the engine, bind the session factory, and create all tables."""
    global engine
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = sa.create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal.configure(bind=engine)

    # Import models so their tables are registered on Base.metadata
    from database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised at {}", db_path)
    return engine
