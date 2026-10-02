from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.otp import ConsoleSmsSender, KeyValueStore, OtpService
from app.core.rbac import Permission, can_access_lot, has_permission
from app.core.redis import get_redis
from app.core.security import InvalidToken, decode_token
from app.db.session import get_db
from app.models import Lot, User

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def get_kv_store() -> KeyValueStore:
    return get_redis()


KvStore = Annotated[KeyValueStore, Depends(get_kv_store)]


def get_otp_service(store: KvStore) -> OtpService:
    settings = get_settings()
    return OtpService(store, ConsoleSmsSender(settings.environment), settings)


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorized
    try:
        user_id = decode_token(creds.credentials, "access")
    except InvalidToken:
        raise unauthorized from None
    # Role is read from the DB, not the token, so role changes and deactivation apply immediately.
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(permission: Permission) -> Callable[..., Coroutine[Any, Any, User]]:
    async def dependency(user: CurrentUser) -> User:
        if not has_permission(user, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return dependency


async def get_accessible_lot(db: AsyncSession, lot_id: int, user: User) -> Lot:
    """404 (not 403) for lots outside the user's scope so lot IDs of other owners aren't revealed."""
    lot = await db.get(Lot, lot_id)
    if lot is None or not can_access_lot(user, lot):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lot not found")
    return lot
