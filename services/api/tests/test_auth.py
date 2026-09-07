from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.models import AuditEvent, Role, RoleName, User, UserRole, UserStatus


def registration_payload(email: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "correct-horse-battery-staple",
        "display_name": "Test Farmer",
        "role": "farmer",
    }


def test_registration_login_refresh_and_me(client, db) -> None:
    registration = client.post("/api/v1/auth/register", json=registration_payload("farmer@example.com"))
    assert registration.status_code == 201
    assert registration.json()["roles"] == ["farmer"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "farmer@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "farmer@example.com"

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert db.scalars(select(AuditEvent).where(AuditEvent.event_type == "auth.registration")).first() is not None


def test_validation_and_role_authorization(client, db) -> None:
    invalid = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "short", "role": "admin"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"

    registration = client.post("/api/v1/auth/register", json=registration_payload("permissions@example.com"))
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "permissions@example.com", "password": "correct-horse-battery-staple"},
    )
    farmer_token = login.json()["access_token"]
    denied = client.get("/api/v1/admin/foundation-status", headers={"Authorization": f"Bearer {farmer_token}"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "insufficient_permissions"

    admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN))
    assert admin_role is not None
    admin = User(
        email="admin@example.com",
        display_name="Test Admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    db.flush()
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    db.commit()

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "correct-horse-battery-staple"},
    )
    assert admin_login.status_code == 200
    allowed = client.get(
        "/api/v1/admin/foundation-status",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "authorized"}
