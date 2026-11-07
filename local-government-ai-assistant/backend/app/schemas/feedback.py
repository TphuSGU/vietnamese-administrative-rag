"""Schemas for citizen feedback and staff handling."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeedbackCategory = Literal["gop_y", "phan_anh", "kien_nghi", "hoi_dap"]
FeedbackStatus = Literal["new", "received", "processing", "resolved", "closed"]


class FeedbackCreate(BaseModel):
    full_name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=255)
    category: FeedbackCategory = "gop_y"
    subject: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=10, max_length=5000)

    @field_validator("full_name", "phone", "email", "subject", "content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class FeedbackUpdate(BaseModel):
    status: Optional[FeedbackStatus] = None
    admin_note: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("admin_note")
    @classmethod
    def strip_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    full_name: str
    phone: str
    email: str
    category: str
    subject: str
    content: str
    status: str
    admin_note: str
    created_at: datetime
    updated_at: datetime


class FeedbackStatusCounts(BaseModel):
    all: int = 0
    new: int = 0
    received: int = 0
    processing: int = 0
    resolved: int = 0
    closed: int = 0


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    status_counts: FeedbackStatusCounts
