import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app    
from app.database import get_db, engine as app_engine, SessionLocal


@pytest.fixture
def db_session():
    """
    Start a Savepoint transaction for each test and roll it back at the end.
    Use the same engine as the app so Postgres indexes and conditions work.
    """
    connection = app_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind = connection,autocommit=False, autoflush=False)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client(db_session):
    """Overide get_db to yield the per-test session"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

    