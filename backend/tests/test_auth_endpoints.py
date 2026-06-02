from app.models.user import User


def test_me_returns_dev_admin_without_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "dev"
    assert response.json()["role"] == "admin"


def test_admin_user_crud_login_me_and_deactivation(client, db):
    created = client.post(
        "/api/auth/users",
        json={
            "username": "planner1",
            "email": "planner1@coficab.local",
            "password": "secret",
            "role": "planner",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    listed = client.get("/api/auth/users")
    assert listed.status_code == 200, listed.text
    assert listed.json()["count"] == 1

    login = client.post(
        "/api/auth/login",
        json={"username": "planner1", "password": "secret"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["role"] == "planner"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "planner1"
    assert me.json()["role"] == "planner"

    patched = client.patch(
        f"/api/auth/users/{user_id}",
        json={"role": "viewer", "is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["role"] == "viewer"
    assert patched.json()["is_active"] is False

    assert db.get(User, user_id).is_active is False
    inactive_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert inactive_me.status_code == 401

    inactive_login = client.post(
        "/api/auth/login",
        json={"username": "planner1", "password": "secret"},
    )
    assert inactive_login.status_code == 401


def test_viewer_token_cannot_manage_users(client):
    created = client.post(
        "/api/auth/users",
        json={"username": "viewer1", "password": "secret", "role": "viewer"},
    )
    assert created.status_code == 201, created.text

    login = client.post(
        "/api/auth/login",
        json={"username": "viewer1", "password": "secret"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    denied = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "blocked", "password": "secret", "role": "viewer"},
    )
    assert denied.status_code == 403
