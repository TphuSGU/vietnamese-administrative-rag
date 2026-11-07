"""Citizen feedback endpoints.

Public users can submit feedback without logging in. Staff/admin users can
list, filter and update handling status.
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_optional_user, require_admin
from app.database.session import get_db
from app.models.db_models import Feedback, User
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
    FeedbackStatusCounts,
    FeedbackUpdate,
)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

VALID_STATUSES = ("new", "received", "processing", "resolved", "closed")


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    feedback = Feedback(
        user_id=user.id if user else None,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        category=payload.category,
        subject=payload.subject,
        content=payload.content,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return FeedbackResponse.model_validate(feedback)


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    status_filter: Literal[
        "all", "new", "received", "processing", "resolved", "closed"
    ] = Query("all", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=255),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FeedbackListResponse:
    filters = []
    if status_filter != "all":
        filters.append(Feedback.status == status_filter)

    search_term = (search or "").strip()
    if search_term:
        pattern = f"%{search_term}%"
        filters.append(
            or_(
                Feedback.subject.ilike(pattern),
                Feedback.content.ilike(pattern),
                Feedback.full_name.ilike(pattern),
                Feedback.phone.ilike(pattern),
                Feedback.email.ilike(pattern),
            )
        )

    base = select(Feedback)
    count_query = select(func.count()).select_from(Feedback)
    if filters:
        base = base.where(*filters)
        count_query = count_query.where(*filters)

    total = await db.scalar(count_query) or 0
    result = await db.scalars(
        base.order_by(Feedback.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(result)

    counts_query = select(Feedback.status, func.count()).group_by(Feedback.status)
    counts = {key: 0 for key in VALID_STATUSES}
    for key, value in (await db.execute(counts_query)).all():
        if key in counts:
            counts[key] = value
    counts["all"] = sum(counts.values())
    total_pages = max(1, (total + page_size - 1) // page_size)

    return FeedbackListResponse(
        items=[FeedbackResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        status_counts=FeedbackStatusCounts(**counts),
    )


@router.patch("/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: UUID,
    payload: FeedbackUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    if payload.status is None and payload.admin_note is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần chọn trạng thái hoặc nhập ghi chú xử lý",
        )

    feedback = await db.get(Feedback, feedback_id)
    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy ý kiến",
        )

    if payload.status is not None:
        feedback.status = payload.status
    if payload.admin_note is not None:
        feedback.admin_note = payload.admin_note

    await db.commit()
    await db.refresh(feedback)
    return FeedbackResponse.model_validate(feedback)
