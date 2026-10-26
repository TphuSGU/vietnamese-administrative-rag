#!/usr/bin/env python3
"""Create relational tables for local development.

Production should use Alembic migrations; this script is the fast path for a
fresh demo database.
"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.database.base import Base  # noqa: E402
from app.database.session import engine  # noqa: E402
import app.models.db_models  # noqa: E402,F401  (register models)


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    print("Đã tạo bảng: users, conversations, messages")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
