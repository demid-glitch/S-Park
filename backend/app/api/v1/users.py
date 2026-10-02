from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, get_accessible_lot, require
from app.core.rbac import Permission
from app.models import Lot, Role, User, Vehicle
from app.schemas.user import StaffCreate, StaffUpdate, UserOut, UserSelfUpdate, VehicleCreate, VehicleOut

router = APIRouter(prefix="/users", tags=["users"])

StaffManager = Annotated[User, Depends(require(Permission.ATTENDANTS_MANAGE))]


@router.get("/me")
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me")
async def update_me(body: UserSelfUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me/vehicles")
async def list_vehicles(user: CurrentUser, db: DbSession) -> list[VehicleOut]:
    rows = await db.scalars(select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.id))
    return [VehicleOut.model_validate(v) for v in rows]


@router.post("/me/vehicles", status_code=status.HTTP_201_CREATED)
async def add_vehicle(body: VehicleCreate, user: CurrentUser, db: DbSession) -> VehicleOut:
    vehicle = Vehicle(user_id=user.id, plate=body.plate, label=body.label)
    db.add(vehicle)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Vehicle already added") from None
    await db.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


@router.delete("/me/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: int, user: CurrentUser, db: DbSession) -> None:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found")
    await db.delete(vehicle)
    await db.commit()


async def _check_staff_assignment(db: DbSession, actor: User, role: Role, lot_id: int | None) -> None:
    if actor.role == Role.OWNER and role != Role.ATTENDANT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owners can only manage attendants")
    if role == Role.ATTENDANT:
        if lot_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Attendants need an assigned lot")
        await get_accessible_lot(db, lot_id, actor)
    elif lot_id is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Only attendants have an assigned lot")


async def _get_managed_user(db: DbSession, actor: User, user_id: int) -> User:
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if actor.role == Role.PLATFORM_ADMIN:
        return target
    # Owners only see attendants working at one of their own lots.
    lot = await db.get(Lot, target.assigned_lot_id) if target.assigned_lot_id else None
    if target.role != Role.ATTENDANT or lot is None or lot.owner_id != actor.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return target


@router.get("")
async def list_users(
    actor: StaffManager,
    db: DbSession,
    role: Role | None = None,
    lot_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserOut]:
    stmt = select(User).order_by(User.id).limit(limit).offset(offset)
    if actor.role == Role.OWNER:
        stmt = stmt.join(Lot, Lot.id == User.assigned_lot_id).where(
            Lot.owner_id == actor.id, User.role == Role.ATTENDANT
        )
    if role is not None:
        stmt = stmt.where(User.role == role)
    if lot_id is not None:
        stmt = stmt.where(User.assigned_lot_id == lot_id)
    return [UserOut.model_validate(u) for u in await db.scalars(stmt)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_staff(body: StaffCreate, actor: StaffManager, db: DbSession) -> UserOut:
    if body.role == Role.CUSTOMER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Customers sign up via OTP")
    await _check_staff_assignment(db, actor, body.role, body.assigned_lot_id)
    user = User(**body.model_dump())
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone already registered") from None
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}")
async def update_staff(user_id: int, body: StaffUpdate, actor: StaffManager, db: DbSession) -> UserOut:
    target = await _get_managed_user(db, actor, user_id)
    if target.id == actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Use /users/me to edit yourself")
    changes = body.model_dump(exclude_unset=True)
    new_role = changes.get("role", target.role)
    if "role" in changes:
        if new_role == Role.CUSTOMER:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot demote staff to customer")
        if new_role != Role.ATTENDANT:
            changes["assigned_lot_id"] = None
    if new_role != Role.CUSTOMER:
        new_lot = changes.get("assigned_lot_id", target.assigned_lot_id)
        await _check_staff_assignment(db, actor, new_role, new_lot)
    for field, value in changes.items():
        setattr(target, field, value)
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)
