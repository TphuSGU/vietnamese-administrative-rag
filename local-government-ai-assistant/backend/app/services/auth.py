"""Authentication service: registration and credential checks."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.db_models import User
from app.repositories import users as user_repo
from app.schemas.auth import UserCreate


class EmailAlreadyExistsError(Exception):
    """Raised when registering an email that is already in use."""


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    existing = await user_repo.get_user_by_email(db, str(payload.email))
    if existing is not None:
        raise EmailAlreadyExistsError("Email đã được đăng ký")

    return await user_repo.create_user(
        db=db,
        email=str(payload.email),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="user",
    )


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    user = await user_repo.get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
