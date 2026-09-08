import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.services.user_service import init_rbac_system

TEST_DB_FILE = "./test_shared.db"
test_engine = create_engine(f"sqlite:///{TEST_DB_FILE}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_files():
    """Ensure test database file is removed after test session."""
    yield
    for f in [TEST_DB_FILE, "./test_auth_api.db", "./test_tender_api.db", "./test_alembic.db"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


@pytest.fixture
def db():
    """Provide a clean isolated DB session for each test and bind it to FastAPI."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    session = TestingSessionLocal()
    init_rbac_system(session)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session

    session.close()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db):
    """Provide a TestClient connected to the current isolated DB session."""
    with TestClient(app) as test_client:
        yield test_client
