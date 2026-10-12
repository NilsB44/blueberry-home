import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db as db_module
from app.config import get_settings
from app.db import get_session
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HUB_COOKIE_SECURE", "false")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db_module, "_engine", engine)
    SQLModel.metadata.create_all(engine)

    def session_override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


ADMIN = {"username": "nils", "display_name": "Nils", "password": "correct horse battery"}


@pytest.fixture
def admin_client(client):
    assert client.post("/api/auth/setup", json=ADMIN).status_code == 201
    return client
