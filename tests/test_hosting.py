import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool

from app.database import make_engine
from app.main import create_app


def test_render_requires_persistent_database(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        make_engine()
    with pytest.raises(ValueError, match="SQLite"):
        make_engine("sqlite:///:memory:")


def test_render_requires_tls_and_releases_postgres_connections(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValueError, match="sslmode"):
        make_engine("postgresql://test:test@localhost/test")
    engine = make_engine("postgresql://test:test@localhost/test?sslmode=require")
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.query["sslmode"] == "require"
    assert isinstance(engine.pool, NullPool)
    engine.dispose()


def test_liveness_does_not_connect_to_database(tmp_path, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    with TestClient(create_app("sqlite:///" + (tmp_path / "test.db").as_posix())) as client:
        def unavailable():
            raise ConnectionError("Database offline")
        monkeypatch.setattr(client.app.state.engine, "connect", unavailable)
        assert client.get("/health/live").status_code == 200
        assert client.get("/health").status_code == 503
