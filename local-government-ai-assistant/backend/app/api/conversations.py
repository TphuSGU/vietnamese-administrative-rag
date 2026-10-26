"""Conversation history endpoints (per authenticated user)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.db_models import User
from app.repositories import conversations as conversation_repo
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
)
from app.services.conversations import (
    get_conversation_detail,
    to_conversation_response,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    title = (payload.title or "Cuộc hội thoại mới").strip()
    conversation = await conversation_repo.create_conversation(
        db, user.id, title=title
    )
    return to_conversation_response(conversation, message_count=0)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    rows = await conversation_repo.list_conversations(db, user.id)
    return [
        to_conversation_response(conversation, message_count=count)
        for conversation, count in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    detail = await get_conversation_detail(db, conversation_id, user.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cuộc hội thoại",
        )
    return detail


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    conversation = await conversation_repo.get_conversation(
        db, conversation_id, user.id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cuộc hội thoại",
        )
    await conversation_repo.delete_conversation(db, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
