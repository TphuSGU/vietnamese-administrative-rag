"""User administration endpoints (admin only)."""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.database.session import get_db
from app.models.db_models import User
from app.repositories import users as user_repo
from app.schemas.auth import (
    RoleUpdate,
    UserListResponse,
    UserResponse,
    UserRoleCounts,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    role: Literal["all", "user", "admin"] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=255),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    search_term = (search or "").strip() or None
    users, total = await user_repo.list_users(
        db,
        role=None if role == "all" else role,
        search=search_term,
        page=page,
        page_size=page_size,
    )
    role_counts = await user_repo.count_users_by_role(db)
    total_pages = max(1, (total + page_size - 1) // page_size)

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        role_counts=UserRoleCounts(**role_counts),
    )


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
