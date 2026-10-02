from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, get_accessible_lot, require
from app.core.rbac import Permission, has_permission, scope_lots
from app.models import Lot, Role, Spot, SpotStatus, Tariff, User, Zone
from app.schemas.lot import (
    LotCreate,
    LotOut,
    LotPublic,
    LotUpdate,
    Occupancy,
    SpotOut,
    SpotsCreate,
    TariffCreate,
    TariffOut,
    TariffUpdate,
    ZoneCreate,
    ZoneOut,
)

router = APIRouter(prefix="/lots", tags=["lots"])


def _require(permission: Permission) -> type[User]:
    return Annotated[User, Depends(require(permission))]  # type: ignore[return-value]


LotCreator = _require(Permission.LOTS_CREATE)
LotUpdater = _require(Permission.LOTS_UPDATE)
SpotReader = _require(Permission.SPOTS_READ)
SpotManager = _require(Permission.SPOTS_MANAGE)
TariffManager = _require(Permission.TARIFFS_MANAGE)


async def _readable_lot(db: AsyncSession, lot_id: int, user: User) -> Lot:
    """Customers may read any active lot; staff only lots in their scope."""
    if user.role == Role.CUSTOMER:
        lot = await db.get(Lot, lot_id)
        if lot is None or not lot.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lot not found")
        return lot
    return await get_accessible_lot(db, lot_id, user)


async def _commit_or_conflict(db: AsyncSession, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from None


@router.get("")
async def list_lots(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LotOut] | list[LotPublic]:
    stmt = select(Lot).order_by(Lot.id).limit(limit).offset(offset)
    if user.role == Role.CUSTOMER:
        rows = await db.scalars(stmt.where(Lot.is_active.is_(True)))
        return [LotPublic.model_validate(lot) for lot in rows]
    rows = await db.scalars(scope_lots(stmt, user))
    return [LotOut.model_validate(lot) for lot in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_lot(body: LotCreate, _: LotCreator, db: DbSession) -> LotOut:
    owner = await db.get(User, body.owner_id)
    if owner is None or owner.role != Role.OWNER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "owner_id must be a parking owner")
    lot = Lot(**body.model_dump())
    db.add(lot)
    await db.commit()
    await db.refresh(lot)
    return LotOut.model_validate(lot)


@router.get("/{lot_id}")
async def get_lot(lot_id: int, user: CurrentUser, db: DbSession) -> LotOut | LotPublic:
    lot = await _readable_lot(db, lot_id, user)
    if user.role == Role.CUSTOMER:
        return LotPublic.model_validate(lot)
    return LotOut.model_validate(lot)


@router.patch("/{lot_id}")
async def update_lot(lot_id: int, body: LotUpdate, user: LotUpdater, db: DbSession) -> LotOut:
    lot = await get_accessible_lot(db, lot_id, user)
    changes = body.model_dump(exclude_unset=True)
    if "commission_percent" in changes and user.role != Role.PLATFORM_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the platform admin sets commission")
    for field, value in changes.items():
        setattr(lot, field, value)
    await db.commit()
    await db.refresh(lot)
    return LotOut.model_validate(lot)


@router.get("/{lot_id}/occupancy")
async def get_occupancy(lot_id: int, user: SpotReader, db: DbSession) -> Occupancy:
    await get_accessible_lot(db, lot_id, user)
    rows = await db.execute(
        select(Spot.status, func.count()).where(Spot.lot_id == lot_id).group_by(Spot.status)
    )
    counts = {s: 0 for s in SpotStatus} | dict(rows.all())
    capacity = sum(counts.values())
    usable = capacity - counts[SpotStatus.OUT_OF_SERVICE]
    taken = counts[SpotStatus.OCCUPIED] + counts[SpotStatus.RESERVED]
    return Occupancy(
        capacity=capacity,
        free=counts[SpotStatus.FREE],
        occupied=counts[SpotStatus.OCCUPIED],
        reserved=counts[SpotStatus.RESERVED],
        out_of_service=counts[SpotStatus.OUT_OF_SERVICE],
        occupancy_percent=round(taken / usable * 100, 1) if usable else 0.0,
    )


@router.get("/{lot_id}/zones")
async def list_zones(lot_id: int, user: SpotReader, db: DbSession) -> list[ZoneOut]:
    await get_accessible_lot(db, lot_id, user)
    rows = await db.scalars(select(Zone).where(Zone.lot_id == lot_id).order_by(Zone.id))
    return [ZoneOut.model_validate(z) for z in rows]


@router.post("/{lot_id}/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(lot_id: int, body: ZoneCreate, user: SpotManager, db: DbSession) -> ZoneOut:
    await get_accessible_lot(db, lot_id, user)
    zone = Zone(lot_id=lot_id, name=body.name)
    db.add(zone)
    await _commit_or_conflict(db, "Zone name already used in this lot")
    await db.refresh(zone)
    return ZoneOut.model_validate(zone)


@router.get("/{lot_id}/spots")
async def list_spots(
    lot_id: int, user: SpotReader, db: DbSession, zone_id: int | None = None
) -> list[SpotOut]:
    await get_accessible_lot(db, lot_id, user)
    stmt = select(Spot).where(Spot.lot_id == lot_id).order_by(Spot.zone_id, Spot.code)
    if zone_id is not None:
        stmt = stmt.where(Spot.zone_id == zone_id)
    return [SpotOut.model_validate(s) for s in await db.scalars(stmt)]


@router.post("/{lot_id}/zones/{zone_id}/spots", status_code=status.HTTP_201_CREATED)
async def create_spots(
    lot_id: int, zone_id: int, body: SpotsCreate, user: SpotManager, db: DbSession
) -> list[SpotOut]:
    await get_accessible_lot(db, lot_id, user)
    zone = await db.get(Zone, zone_id)
    if zone is None or zone.lot_id != lot_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    codes = [c.strip().upper() for c in body.codes]
    if len(set(codes)) != len(codes) or not all(codes):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Spot codes must be unique and non-empty")
    spots = [Spot(lot_id=lot_id, zone_id=zone_id, code=code, is_ev=body.is_ev) for code in codes]
    db.add_all(spots)
    await _commit_or_conflict(db, "A spot code already exists in this lot")
    return [SpotOut.model_validate(s) for s in spots]


@router.get("/{lot_id}/tariffs")
async def list_tariffs(lot_id: int, user: CurrentUser, db: DbSession) -> list[TariffOut]:
    await _readable_lot(db, lot_id, user)
    stmt = select(Tariff).where(Tariff.lot_id == lot_id).order_by(Tariff.id)
    if not has_permission(user, Permission.TARIFFS_MANAGE):
        stmt = stmt.where(Tariff.is_active.is_(True))
    return [TariffOut.model_validate(t) for t in await db.scalars(stmt)]


@router.post("/{lot_id}/tariffs", status_code=status.HTTP_201_CREATED)
async def create_tariff(lot_id: int, body: TariffCreate, user: TariffManager, db: DbSession) -> TariffOut:
    await get_accessible_lot(db, lot_id, user)
    tariff = Tariff(lot_id=lot_id, **body.model_dump())
    db.add(tariff)
    await db.commit()
    await db.refresh(tariff)
    return TariffOut.model_validate(tariff)


@router.patch("/{lot_id}/tariffs/{tariff_id}")
async def update_tariff(
    lot_id: int, tariff_id: int, body: TariffUpdate, user: TariffManager, db: DbSession
) -> TariffOut:
    await get_accessible_lot(db, lot_id, user)
    tariff = await db.get(Tariff, tariff_id)
    if tariff is None or tariff.lot_id != lot_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tariff not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tariff, field, value)
    await db.commit()
    await db.refresh(tariff)
    return TariffOut.model_validate(tariff)
