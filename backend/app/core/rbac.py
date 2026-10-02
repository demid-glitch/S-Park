"""Role permissions and lot scoping.

Two layers, both required:
1. Permission: may this role perform the action at all?
2. Scope: is this particular lot one the user is allowed to touch?
Owners only reach lots they own; attendants only their assigned lot.
"""

import enum

from sqlalchemy import Select, false

from app.models import Lot, Role, User


class Permission(str, enum.Enum):
    LOTS_CREATE = "lots:create"
    LOTS_UPDATE = "lots:update"
    LOTS_READ_ALL = "lots:read_all"
    SPOTS_MANAGE = "spots:manage"
    SPOTS_READ = "spots:read"
    TARIFFS_MANAGE = "tariffs:manage"
    USERS_MANAGE = "users:manage"
    ATTENDANTS_MANAGE = "attendants:manage"
    PARKING_SESSIONS_MANAGE = "parking_sessions:manage"
    CASH_RECORD = "cash:record"
    SHIFT_OWN = "shift:own"
    SHIFTS_CONFIRM = "shifts:confirm"
    INCOME_READ = "income:read"
    PAYMENTS_READ_ALL = "payments:read_all"
    REFUNDS_MANAGE = "refunds:manage"
    PAYOUTS_MANAGE = "payouts:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PLATFORM_ADMIN: frozenset(Permission),
    Role.OWNER: frozenset(
        {
            Permission.LOTS_UPDATE,
            Permission.SPOTS_MANAGE,
            Permission.SPOTS_READ,
            Permission.TARIFFS_MANAGE,
            Permission.ATTENDANTS_MANAGE,
            Permission.SHIFTS_CONFIRM,
            Permission.INCOME_READ,
        }
    ),
    Role.ATTENDANT: frozenset(
        {
            Permission.SPOTS_READ,
            Permission.PARKING_SESSIONS_MANAGE,
            Permission.CASH_RECORD,
            Permission.SHIFT_OWN,
        }
    ),
    Role.CUSTOMER: frozenset(),
}


def has_permission(user: User, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())


def can_access_lot(user: User, lot: Lot) -> bool:
    if user.role == Role.PLATFORM_ADMIN:
        return True
    if user.role == Role.OWNER:
        return lot.owner_id == user.id
    if user.role == Role.ATTENDANT:
        return lot.id == user.assigned_lot_id
    return False


def scope_lots(stmt: Select, user: User) -> Select:
    """Restricts a query over Lot to the lots this staff user may see."""
    if user.role == Role.PLATFORM_ADMIN:
        return stmt
    if user.role == Role.OWNER:
        return stmt.where(Lot.owner_id == user.id)
    if user.role == Role.ATTENDANT:
        if user.assigned_lot_id is None:
            return stmt.where(false())
        return stmt.where(Lot.id == user.assigned_lot_id)
    return stmt.where(false())
