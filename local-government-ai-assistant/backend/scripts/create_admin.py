#!/usr/bin/env python3
"""Create or promote an admin account.

Usage:
    python scripts/create_admin.py --email admin@example.com --password Secret123
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.core.security import hash_password  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.repositories import users as user_repo  # noqa: E402


async def main(email: str, password: str, full_name: str) -> None:
    async with SessionLocal() as db:
        user = await user_repo.get_user_by_email(db, email)
        if user is None:
            user = await user_repo.create_user(
                db,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role="admin",
            )
            print(f"Đã tạo admin: {user.email}")
        else:
            user.role = "admin"
            user.is_active = True
            await db.commit()
            print(f"Đã nâng quyền admin: {user.email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Quản trị viên")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.password, args.full_name))
