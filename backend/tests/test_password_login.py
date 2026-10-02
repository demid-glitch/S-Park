import pytest

from app.core.passwords import hash_password, verify_password
from app.models import Role
from tests.conftest import auth

PASSWORD = "correct-horse-battery"


def test_hash_roundtrip():
    h = hash_password(PASSWORD)
    assert h.startswith("scrypt$") and PASSWORD not in h
    assert verify_password(PASSWORD, h)
    assert not verify_password("wrong", h)
    assert not verify_password(PASSWORD, "garbage")


@pytest.fixture
async def admin(factory):
    user = await factory.user(Role.PLATFORM_ADMIN)
    user.phone, user.username, user.password_hash = None, "admin_1", hash_password(PASSWORD)
    await factory.db.commit()
    return user


async def _login(client, username, password):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def test_login_success_case_insensitive(client, admin):
    r = await _login(client, "Admin_1", PASSWORD)
    assert r.status_code == 200
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["username"] == "admin_1" and me.json()["role"] == "platform_admin"


async def test_login_failures(client, admin):
    assert (await _login(client, "admin_1", "nope")).status_code == 401
    assert (await _login(client, "nobody", PASSWORD)).status_code == 401


async def test_login_lockout(client, admin):
    for _ in range(10):
        assert (await _login(client, "admin_1", "nope")).status_code == 401
    assert (await _login(client, "admin_1", PASSWORD)).status_code == 429


async def test_login_disabled(client, admin, db):
    admin.is_active = False
    await db.commit()
    assert (await _login(client, "admin_1", PASSWORD)).status_code == 403


async def test_change_password(client, admin):
    h = auth(admin)
    bad = {"current_password": "nope", "new_password": "another-long-one"}
    assert (await client.post("/api/v1/auth/password", json=bad, headers=h)).status_code == 400
    short = {"current_password": PASSWORD, "new_password": "short"}
    assert (await client.post("/api/v1/auth/password", json=short, headers=h)).status_code == 422
    ok = {"current_password": PASSWORD, "new_password": "another-long-one"}
    assert (await client.post("/api/v1/auth/password", json=ok, headers=h)).status_code == 204
    assert (await _login(client, "admin_1", PASSWORD)).status_code == 401
    assert (await _login(client, "admin_1", "another-long-one")).status_code == 200


async def test_customer_without_password_cannot_password_login(client, factory):
    customer = await factory.user(Role.CUSTOMER)
    customer.username = "cust"
    await factory.db.commit()
    assert (await _login(client, "cust", "")).status_code == 401
