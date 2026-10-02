"""S-Park admin commands.

  python -m app.cli create-admin --username NAME [--phone PHONE] [--name "Full Name"]
      Creates or updates a platform admin. Prompts for the password.

  python -m app.cli bootstrap-admin
      Creates the admin from INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD if that
      username doesn't exist yet. Safe to run on every deploy: never overwrites a password.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.normalize import normalize_phone, normalize_username
from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models import Role, User

MIN_PASSWORD_LENGTH = 10


async def upsert_admin(
    username: str, password: str | None, phone: str | None, full_name: str | None, overwrite: bool
) -> None:
    username = normalize_username(username)
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == username))
        if user is not None and not overwrite:
            print(f"admin '{username}' already exists; leaving it unchanged")
            return
        if user is None:
            user = User(username=username)
            db.add(user)
        user.role, user.assigned_lot_id, user.is_active = Role.PLATFORM_ADMIN, None, True
        if password:
            user.password_hash = hash_password(password)
        if phone:
            user.phone = normalize_phone(phone)
        if full_name:
            user.full_name = full_name
        await db.commit()
        print(f"platform admin '{username}' ready (id={user.id})")


def _check_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--username", required=True)
    create.add_argument("--phone")
    create.add_argument("--name")
    sub.add_parser("bootstrap-admin")
    args = parser.parse_args()

    if args.command == "create-admin":
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
        asyncio.run(upsert_admin(args.username, _check_password(password), args.phone, args.name, overwrite=True))
    else:
        username = os.environ.get("INITIAL_ADMIN_USERNAME")
        password = os.environ.get("INITIAL_ADMIN_PASSWORD")
        if not username or not password:
            print("INITIAL_ADMIN_USERNAME/PASSWORD not set; skipping admin bootstrap")
            return
        asyncio.run(upsert_admin(username, _check_password(password), None, None, overwrite=False))


if __name__ == "__main__":
    main()
