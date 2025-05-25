import pytest
from fastapi.testclient import TestClient
from user_service.main import app

client = TestClient(app)

def test_register_user():
    payload = {
        "login": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    }
    response = client.post("/users/register", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "id" in data
    assert data["login"] == "testuser"
    assert data["email"] == "test@example.com"

def test_login_user():
    response = client.post("/auth/login", data={
        "username": "testuser",
        "password": "testpass"
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    global token
    token = data["access_token"]

def test_get_profile():
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["login"] == "testuser"
    assert data["email"] == "test@example.com"

def test_update_profile():
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "first_name": "John",
        "last_name": "Doe"
    }
    response = client.put("/users/me", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"