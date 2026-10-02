from app.core.security import create_access_token
from app.models import Role
from tests.conftest import auth

PHONE = "99112233"
E164 = "+97699112233"


async def _login(client, sms) -> dict:
    assert (await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})).status_code == 202
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": sms.sent[E164]})
    assert r.status_code == 200, r.text
    return r.json()


async def test_otp_signup_creates_customer(client, sms):
    tokens = await _login(client, sms)
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["phone"] == E164
    assert r.json()["role"] == "customer"


async def test_otp_existing_staff_keeps_role(client, sms, factory):
    admin = await factory.user(Role.PLATFORM_ADMIN)
    admin.phone = E164
    await factory.db.commit()
    tokens = await _login(client, sms)
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.json()["role"] == "platform_admin"


async def test_otp_resend_cooldown(client):
    assert (await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})).status_code == 202
    assert (await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})).status_code == 429


async def test_otp_wrong_code_and_lockout(client, sms):
    await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    good = sms.sent[E164]
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        r = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": bad})
        assert r.status_code == 400
    # Attempt budget exhausted: even the right code is refused now.
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": good})
    assert r.status_code == 400


async def test_otp_code_single_use(client, sms):
    await _login(client, sms)
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": sms.sent[E164]})
    assert r.status_code == 400


async def test_invalid_phone_rejected(client):
    assert (await client.post("/api/v1/auth/otp/request", json={"phone": "12"})).status_code == 422


async def test_refresh(client, sms):
    tokens = await _login(client, sms)
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # An access token must not work as a refresh token, and vice versa.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401


async def test_missing_and_garbage_token(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    r = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


async def test_deactivated_user_rejected(client, factory):
    user = await factory.user(Role.CUSTOMER, is_active=False)
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {create_access_token(user.id)}"})
    assert r.status_code == 401


async def test_vehicles(client, factory):
    user = await factory.user(Role.CUSTOMER)
    h = auth(user)
    r = await client.post("/api/v1/users/me/vehicles", json={"plate": "1234 уба"}, headers=h)
    assert r.status_code == 201
    assert r.json()["plate"] == "1234УБА"
    r = await client.post("/api/v1/users/me/vehicles", json={"plate": "1234УБА"}, headers=h)
    assert r.status_code == 409
    vid = (await client.get("/api/v1/users/me/vehicles", headers=h)).json()[0]["id"]

    other = await factory.user(Role.CUSTOMER)
    assert (await client.delete(f"/api/v1/users/me/vehicles/{vid}", headers=auth(other))).status_code == 404
    assert (await client.delete(f"/api/v1/users/me/vehicles/{vid}", headers=h)).status_code == 204
