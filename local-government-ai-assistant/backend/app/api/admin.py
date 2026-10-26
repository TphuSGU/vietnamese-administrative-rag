"""Admin dashboard endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.core.dependencies import get_vector_store
from app.database.session import get_db
from app.database.vector_store import VectorStore
from app.models.db_models import Conversation, Message, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    users = await db.scalar(select(func.count()).select_from(User))
    conversations = await db.scalar(
        select(func.count()).select_from(Conversation)
    )
    messages = await db.scalar(select(func.count()).select_from(Message))

    return {
        "users": users or 0,
        "conversations": conversations or 0,
        "messages": messages or 0,
        "document_chunks": vector_store.count(),
    }
