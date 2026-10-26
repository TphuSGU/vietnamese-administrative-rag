"""User administration endpoints (admin only)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.database.session import get_db
from app.models.db_models import User
from app.repositories import users as user_repo
from app.schemas.auth import RoleUpdate, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    users = await user_repo.list_users(db)
    return [UserResponse.model_validate(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: UUID,
    payload: RoleUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await user_repo.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng",
        )
    updated = await user_repo.update_user_role(db, user, payload.role)
    return UserResponse.model_validate(updated)
