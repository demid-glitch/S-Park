"""Usage: python -m app.cli create-admin <phone> [full name]"""

import asyncio
import sys

from sqlalchemy import select

from app.core.normalize import normalize_phone
from app.db.session import SessionLocal
from app.models import Role, User


async def create_admin(phone: str, full_name: str | None) -> None:
    phone = normalize_phone(phone)
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.phone == phone))
        if user is None:
            user = User(phone=phone)
            db.add(user)
        user.role, user.assigned_lot_id, user.is_active = Role.PLATFORM_ADMIN, None, True
        if full_name:
            user.full_name = full_name
        await db.commit()
        print(f"{phone} is now a platform admin (id={user.id})")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "create-admin":
        sys.exit(__doc__)
    asyncio.run(create_admin(sys.argv[2], " ".join(sys.argv[3:]) or None))


if __name__ == "__main__":
    main()
