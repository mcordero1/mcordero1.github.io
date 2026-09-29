from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import ProfileRecord, initialize, read_profile, save_profile
from app.main import create_app
from app.schemas import Profile
import pytest


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app("sqlite:///" + (tmp_path / "test.db").as_posix())) as client:
        yield client


def test_profile_rendered_and_assets_available(client):
    result = client.get("/")
    assert result.status_code == 200
    assert "Marcos Cordero Tenreyro" in result.text
    assert "Centaurus Securities" in result.text
    assert 'lang="es"' in result.text
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/favicon.svg").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_database_changes_visible_without_restart(client):
    engine = client.app.state.engine
    with Session(engine) as session, session.begin():
        row = session.get(ProfileRecord, 1)
        row.content = {**row.content, "role": "Product Lead de prueba"}
    assert client.get("/api/v1/profile").json()["role"] == "Product Lead de prueba"
    assert "Product Lead de prueba" in client.get("/").text
    assert client.get("/").headers["cache-control"] == "no-store"


def test_initialize_does_not_overwrite_updates(client):
    engine = client.app.state.engine
    profile = read_profile(engine)
    profile.role = "Perfil editado"
    save_profile(engine, profile)
    initialize(engine)
    assert read_profile(engine).role == "Perfil editado"


def test_user_content_escaped_and_public_write_disabled(client):
    engine = client.app.state.engine
    profile = read_profile(engine)
    profile.introduction = '<script>alert("xss")</script>'
    save_profile(engine, profile)
    html = client.get("/").text
    assert '<script>alert("xss")</script>' not in html
    assert "&lt;script&gt;" in html
    assert client.put("/api/v1/profile", json={"role": "changed"}).status_code == 405
    assert client.get("/.env").status_code == 404
    assert client.get("/data/profile.db").status_code == 404


def test_invalid_contact_values_rejected(client):
    data = client.get("/api/v1/profile").json()
    with pytest.raises(ValueError):
        Profile.model_validate({**data, "linkedin": "javascript:alert(1)"})
    with pytest.raises(ValueError):
        Profile.model_validate({**data, "email": "me@example.com?bcc=other@example.com"})
    with pytest.raises(ValueError):
        Profile.model_validate({**data, "unknown_field": "typo"})
