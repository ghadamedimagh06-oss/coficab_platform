import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

os.environ.setdefault("WATCHER_ENABLED", "0")
os.environ.setdefault("SCHEDULER_ENABLED", "0")
# Keep the rate limiter + login lockout out of the way of the suite (many rapid
# TestClient calls / repeated bad-login assertions).
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("LOGIN_LOCKOUT_ENABLED", "0")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEV_AUTH_BYPASS", "1")

# Configuration de la base de données de test
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Crée les tables de test"""
    from app.database import Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield
    Base.metadata.drop_all(bind=engine, checkfirst=True)


@pytest.fixture
def db():
    """Fournit une session de base de données de test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """Fournit un client de test FastAPI"""
    from app.main import app
    from app.database import get_db, get_db_optional

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_optional] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
