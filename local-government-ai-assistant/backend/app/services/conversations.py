"""Conversation service helpers (ownership + response shaping)."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Conversation
from app.repositories import conversations as conversation_repo
from app.schemas.conversation import (
    ConversationDetail,
    ConversationResponse,
    MessageResponse,
)


def to_conversation_response(
    conversation: Conversation, message_count: int = 0
) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
    )


async def get_conversation_detail(
    db: AsyncSession, conversation_id: UUID, user_id: UUID
) -> ConversationDetail | None:
    conversation = await conversation_repo.get_conversation(
        db, conversation_id, user_id
    )
    if conversation is None:
        return None

    messages = await conversation_repo.list_messages(db, conversation_id)
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages),
        messages=[
            MessageResponse.model_validate(message) for message in messages
        ],
    )


def sources_payload(source_chunks: list[Any]) -> list[dict[str, Any]]:
    """Keep only JSON-serialisable citation fields for message history."""
    payload: list[dict[str, Any]] = []
    for chunk in source_chunks or []:
        if hasattr(chunk, "model_dump"):
            data = chunk.model_dump()
        elif isinstance(chunk, dict):
            data = chunk
        else:
            continue
        payload.append(
            {
                "document_id": data.get("document_id"),
                "chunk_index": data.get("chunk_index"),
                "similarity_score": data.get("similarity_score"),
                "text": data.get("text"),
            }
        )
    return payload
