"""Database access for users."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import User


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    return await db.get(User, user_id)


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    full_name: str = "",
    role: str = "user",
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession,
    role: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[User], int]:
    conditions = []
    if role in {"user", "admin"}:
        conditions.append(User.role == role)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
        )

    count_stmt = select(func.count()).select_from(User)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = await db.scalar(count_stmt) or 0

    stmt = select(User)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = (
        stmt.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def count_users_by_role(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    counts = {"all": 0, "admin": 0, "user": 0}
    for role, count in result.all():
        counts[role] = count
        counts["all"] += count
    return counts


async def update_user_role(db: AsyncSession, user: User, role: str) -> User:
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user
