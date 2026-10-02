import os

os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.deps import get_otp_service  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.otp import OtpService  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Lot, Role, User  # noqa: E402

# Set TEST_DATABASE_URL to a throwaway Postgres DB to run the suite against Postgres.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")


class FakeStore:
    """In-memory stand-in for the subset of Redis that OtpService uses (TTL ignored)."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(self, name: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and name in self.data:
            return None
        self.data[name] = value
        return True

    async def get(self, name: str) -> str | None:
        return self.data.get(name)

    async def incr(self, name: str) -> int:
        self.data[name] = str(int(self.data.get(name, "0")) + 1)
        return int(self.data[name])

    async def expire(self, name: str, time: int) -> bool:
        return name in self.data

    async def delete(self, *names: str) -> int:
        return sum(self.data.pop(n, None) is not None for n in names)


class CapturingSms:
    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send(self, phone: str, message: str) -> None:
        self.sent[phone] = message.rsplit(" ", 1)[-1]


@pytest.fixture
async def engine():
    kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if "sqlite" in TEST_DATABASE_URL else {}
    eng = create_async_engine(TEST_DATABASE_URL, **kwargs)
    if "sqlite" in TEST_DATABASE_URL:
        @event.listens_for(eng.sync_engine, "connect")
        def _fk_on(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
def sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(sessionmaker) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session


@pytest.fixture
def sms() -> CapturingSms:
    return CapturingSms()


@pytest.fixture
async def client(sessionmaker, sms) -> AsyncIterator[AsyncClient]:
    app = create_app()
    store = FakeStore()

    async def _db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_otp_service] = lambda: OtpService(store, sms, get_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class Factory:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._n = 0

    async def user(self, role: Role, lot: Lot | None = None, **kw) -> User:
        self._n += 1
        user = User(phone=f"+9769900{self._n:04d}", role=role, assigned_lot_id=lot.id if lot else None, **kw)
        self.db.add(user)
        await self.db.commit()
        return user

    async def lot(self, owner: User, **kw) -> Lot:
        lot = Lot(owner_id=owner.id, name=kw.pop("name", f"Lot {owner.id}"), **kw)
        self.db.add(lot)
        await self.db.commit()
        return lot


@pytest.fixture
def factory(db) -> Factory:
    return Factory(db)


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}
