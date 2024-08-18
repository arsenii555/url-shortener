import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .main import app, get_db
from .database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def run_around_tests():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Welcome to URL Shortener API!"


def test_create_url():
    url_data = {"target_url": "https://example.com"}
    response = client.post("/url", json=url_data)
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "admin_url" in data


def test_create_url_invalid():
    url_data = {"target_url": "invalid-url"}
    response = client.post("/url", json=url_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid URL provided"}


def test_forward_to_target_url():
    url_data = {"target_url": "https://example.com"}
    response = client.post("/url", json=url_data)
    assert response.status_code == 200
    url_key = response.json()["url"].split("/")[-1]
    forward_response = client.get(f"/{url_key}")
    assert forward_response.status_code == 200
    assert forward_response.history[0].status_code == 307
    assert forward_response.url == "https://example.com"


def test_forward_to_nonexistent_url():
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "URL 'http://testserver/nonexistent' doesn't exist"}


def test_get_url_info():
    url_data = {"target_url": "https://example.com"}
    response = client.post("/url", json=url_data)
    assert response.status_code == 200
    secret_key = response.json()["admin_url"].split("/")[-1]

    admin_response = client.get(f"/admin/{secret_key}")
    assert admin_response.status_code == 200
    data = admin_response.json()
    assert data["target_url"] == "https://example.com"


def test_get_url_info_nonexistent():
    response = client.get("/admin/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "URL 'http://testserver/admin/nonexistent' doesn't exist"}


def test_delete_url():
    url_data = {"target_url": "https://example.com"}
    response = client.post("/url", json=url_data)
    assert response.status_code == 200
    secret_key = response.json()["admin_url"].split("/")[-1]

    delete_response = client.delete(f"/admin/{secret_key}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"detail": f"Successfully deleted shortenrd URL for 'https://example.com'"}


def test_delete_url_nonexistent():
    response = client.delete("/admin/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "URL 'http://testserver/admin/nonexistent' doesn't exist"}
