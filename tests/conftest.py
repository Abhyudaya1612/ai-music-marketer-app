"""Test configuration and fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.database import Base


@pytest.fixture(scope="function")
def db() -> Session:
    """Create an in-memory SQLite database for testing."""
    # Use check_same_thread=False for testing with TestClient which uses threads
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
