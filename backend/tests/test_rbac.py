import pytest
from sqlalchemy import select

from app.models import Role, Spot, SpotStatus, Zone
from tests.conftest import auth


@pytest.fixture
async def world(factory):
    """Two owners with one lot each, an attendant at lot A, an admin and a customer."""
    admin = await factory.user(Role.PLATFORM_ADMIN)
    owner_a = await factory.user(Role.OWNER)
    owner_b = await factory.user(Role.OWNER)
    lot_a = await factory.lot(owner_a, commission_percent=5)
    lot_b = await factory.lot(owner_b)
    attendant = await factory.user(Role.ATTENDANT, lot=lot_a)
    customer = await factory.user(Role.CUSTOMER)
    return {
        "admin": admin, "owner_a": owner_a, "owner_b": owner_b,
        "lot_a": lot_a, "lot_b": lot_b, "attendant": attendant, "customer": customer,
    }


async def test_only_admin_creates_lots(client, world):
    body = {"owner_id": world["owner_a"].id, "name": "Sukhbaatar Square"}
    assert (await client.post("/api/v1/lots", json=body, headers=auth(world["owner_a"]))).status_code == 403
    assert (await client.post("/api/v1/lots", json=body, headers=auth(world["attendant"]))).status_code == 403
    r = await client.post("/api/v1/lots", json=body, headers=auth(world["admin"]))
    assert r.status_code == 201
    assert r.json()["owner_id"] == world["owner_a"].id


async def test_lot_owner_must_be_owner_role(client, world):
    body = {"owner_id": world["customer"].id, "name": "X"}
    assert (await client.post("/api/v1/lots", json=body, headers=auth(world["admin"]))).status_code == 422


async def test_lot_list_is_scoped(client, world):
    ids = lambda r: {lot["id"] for lot in r.json()}  # noqa: E731
    a, b = world["lot_a"].id, world["lot_b"].id
    assert ids(await client.get("/api/v1/lots", headers=auth(world["admin"]))) == {a, b}
    assert ids(await client.get("/api/v1/lots", headers=auth(world["owner_a"]))) == {a}
    assert ids(await client.get("/api/v1/lots", headers=auth(world["owner_b"]))) == {b}
    assert ids(await client.get("/api/v1/lots", headers=auth(world["attendant"]))) == {a}


async def test_owner_cannot_reach_other_owners_lot(client, world):
    h, b = auth(world["owner_a"]), world["lot_b"].id
    assert (await client.get(f"/api/v1/lots/{b}", headers=h)).status_code == 404
    assert (await client.patch(f"/api/v1/lots/{b}", json={"name": "mine"}, headers=h)).status_code == 404
    assert (await client.get(f"/api/v1/lots/{b}/occupancy", headers=h)).status_code == 404
    tariff = {"name": "Hourly", "kind": "hourly", "rate": 1000}
    assert (await client.post(f"/api/v1/lots/{b}/tariffs", json=tariff, headers=h)).status_code == 404


async def test_customer_sees_public_active_lots_only(client, world, db):
    world["lot_b"].is_active = False
    await db.commit()
    r = await client.get("/api/v1/lots", headers=auth(world["customer"]))
    assert [lot["id"] for lot in r.json()] == [world["lot_a"].id]
    assert "commission_percent" not in r.json()[0]
    assert (await client.get(f"/api/v1/lots/{world['lot_b'].id}", headers=auth(world["customer"]))).status_code == 404
    assert (await client.get(f"/api/v1/lots/{world['lot_a'].id}/occupancy", headers=auth(world["customer"]))).status_code == 403


async def test_owner_cannot_change_commission(client, world):
    a = world["lot_a"].id
    r = await client.patch(f"/api/v1/lots/{a}", json={"commission_percent": 0}, headers=auth(world["owner_a"]))
    assert r.status_code == 403
    r = await client.patch(f"/api/v1/lots/{a}", json={"name": "New name"}, headers=auth(world["owner_a"]))
    assert r.status_code == 200
    r = await client.patch(f"/api/v1/lots/{a}", json={"commission_percent": 7.5}, headers=auth(world["admin"]))
    assert r.status_code == 200 and r.json()["commission_percent"] == "7.50"


async def test_tariffs_owner_manages_attendant_cannot(client, world):
    a = world["lot_a"].id
    tariff = {"name": "Hourly", "kind": "hourly", "rate": 2000, "free_minutes": 15, "daily_cap": 20000}
    assert (await client.post(f"/api/v1/lots/{a}/tariffs", json=tariff, headers=auth(world["attendant"]))).status_code == 403
    r = await client.post(f"/api/v1/lots/{a}/tariffs", json=tariff, headers=auth(world["owner_a"]))
    assert r.status_code == 201
    tid = r.json()["id"]
    r = await client.patch(f"/api/v1/lots/{a}/tariffs/{tid}", json={"rate": 1}, headers=auth(world["attendant"]))
    assert r.status_code == 403
    # Customers and attendants can read active tariffs.
    for who in ("customer", "attendant"):
        r = await client.get(f"/api/v1/lots/{a}/tariffs", headers=auth(world[who]))
        assert r.status_code == 200 and len(r.json()) == 1


async def test_daily_cap_only_on_hourly(client, world):
    a = world["lot_a"].id
    tariff = {"name": "Day", "kind": "daily", "rate": 15000, "daily_cap": 1}
    assert (await client.post(f"/api/v1/lots/{a}/tariffs", json=tariff, headers=auth(world["owner_a"]))).status_code == 422


async def test_zones_spots_and_occupancy(client, world, db):
    a, h = world["lot_a"].id, auth(world["owner_a"])
    zone = (await client.post(f"/api/v1/lots/{a}/zones", json={"name": "A"}, headers=h)).json()
    r = await client.post(f"/api/v1/lots/{a}/zones/{zone['id']}/spots", json={"codes": ["a1", "A2", "A3", "A4"]}, headers=h)
    assert r.status_code == 201 and [s["code"] for s in r.json()] == ["A1", "A2", "A3", "A4"]
    r = await client.post(f"/api/v1/lots/{a}/zones/{zone['id']}/spots", json={"codes": ["A1"]}, headers=h)
    assert r.status_code == 409
    # Attendant may read spots but not create them.
    r = await client.post(f"/api/v1/lots/{a}/zones/{zone['id']}/spots", json={"codes": ["B1"]}, headers=auth(world["attendant"]))
    assert r.status_code == 403
    assert len((await client.get(f"/api/v1/lots/{a}/spots", headers=auth(world["attendant"]))).json()) == 4

    spots = (await db.scalars(select(Spot).where(Spot.lot_id == a).order_by(Spot.code))).all()
    for spot, st in zip(spots, [SpotStatus.OCCUPIED, SpotStatus.RESERVED, SpotStatus.OUT_OF_SERVICE], strict=False):
        spot.status = st
    await db.commit()

    r = await client.get(f"/api/v1/lots/{a}/occupancy", headers=auth(world["attendant"]))
    assert r.json() == {
        "capacity": 4, "free": 1, "occupied": 1, "reserved": 1, "out_of_service": 1,
        "occupancy_percent": 66.7,
    }


async def test_zone_from_other_lot_rejected(client, world, db):
    zone_b = Zone(lot_id=world["lot_b"].id, name="B")
    db.add(zone_b)
    await db.commit()
    r = await client.post(
        f"/api/v1/lots/{world['lot_a'].id}/zones/{zone_b.id}/spots",
        json={"codes": ["X1"]}, headers=auth(world["owner_a"]),
    )
    assert r.status_code == 404


async def test_owner_manages_only_own_attendants(client, world):
    h = auth(world["owner_a"])
    body = {"phone": "88001122", "full_name": "Bat", "role": "attendant", "assigned_lot_id": world["lot_a"].id}
    r = await client.post("/api/v1/users", json=body, headers=h)
    assert r.status_code == 201
    new_id = r.json()["id"]

    # Not for someone else's lot, and not other roles.
    r = await client.post("/api/v1/users", json=body | {"phone": "88001123", "assigned_lot_id": world["lot_b"].id}, headers=h)
    assert r.status_code == 404
    r = await client.post("/api/v1/users", json={"phone": "88001124", "full_name": "X", "role": "owner"}, headers=h)
    assert r.status_code == 403
    r = await client.post("/api/v1/users", json=body | {"phone": "88001125", "assigned_lot_id": None}, headers=h)
    assert r.status_code == 422

    ids = {u["id"] for u in (await client.get("/api/v1/users", headers=h)).json()}
    assert ids == {world["attendant"].id, new_id}
    assert (await client.get("/api/v1/users", headers=auth(world["owner_b"]))).json() == []

    # owner_b can't touch owner_a's attendant; owner_a can't move them to lot_b or promote them.
    assert (await client.patch(f"/api/v1/users/{new_id}", json={"is_active": False}, headers=auth(world["owner_b"]))).status_code == 404
    assert (await client.patch(f"/api/v1/users/{new_id}", json={"assigned_lot_id": world["lot_b"].id}, headers=h)).status_code == 404
    assert (await client.patch(f"/api/v1/users/{new_id}", json={"role": "owner"}, headers=h)).status_code == 403
    r = await client.patch(f"/api/v1/users/{new_id}", json={"is_active": False}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False


async def test_attendant_and_customer_cannot_manage_users(client, world):
    for who in ("attendant", "customer"):
        assert (await client.get("/api/v1/users", headers=auth(world[who]))).status_code == 403


async def test_admin_promotes_and_reassigns(client, world):
    h = auth(world["admin"])
    cid = world["customer"].id
    r = await client.patch(f"/api/v1/users/{cid}", json={"role": "owner"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "owner"
    # Changing an attendant to owner clears the lot assignment.
    r = await client.patch(f"/api/v1/users/{world['attendant'].id}", json={"role": "owner"}, headers=h)
    assert r.json()["assigned_lot_id"] is None
    r = await client.patch(f"/api/v1/users/{cid}", json={"role": "customer"}, headers=h)
    assert r.status_code == 422
    r = await client.patch(f"/api/v1/users/{world['admin'].id}", json={"is_active": False}, headers=h)
    assert r.status_code == 403
