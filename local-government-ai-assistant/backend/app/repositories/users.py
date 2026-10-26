"""Database access for users."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
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


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def update_user_role(db: AsyncSession, user: User, role: str) -> User:
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user
