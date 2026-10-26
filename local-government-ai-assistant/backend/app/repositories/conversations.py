"""Database access for conversations and messages."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Conversation, Message


async def create_conversation(
    db: AsyncSession, user_id: UUID, title: str = ""
) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title[:255])
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_conversations(
    db: AsyncSession, user_id: UUID
) -> list[tuple[Conversation, int]]:
    result = await db.execute(
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def get_conversation(
    db: AsyncSession, conversation_id: UUID, user_id: UUID
) -> Optional[Conversation]:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_conversation(db: AsyncSession, conversation: Conversation) -> None:
    await db.delete(conversation)
    await db.commit()


async def add_message(
    db: AsyncSession,
    conversation_id: UUID,
    role: str,
    content: str,
    sources: Optional[list] = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Touch the parent so conversation lists sort by latest activity.
    conversation = await db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = message.created_at
        await db.commit()

    return message


async def list_messages(
    db: AsyncSession, conversation_id: UUID
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
