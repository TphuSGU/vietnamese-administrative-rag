"""Pydantic response models for the locality reference endpoints (Phase 9).

Demo contract: no URL fields anywhere — source_url/pdf_url/portal stay
internal. UI renders citation + số hiệu + ngày + cơ quan only (plan §8.3).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class LocalityBrief(BaseModel):
    """Mã/nombre of the locality (portal URL deliberately excluded)."""

    code: str
    name: str
    level: str = ""
    parent: str = ""


class ContactInfo(BaseModel):
    address: str = ""
    phone: str = ""
    email: str = ""


class WorkingHours(BaseModel):
    weekdays: str = ""
    saturday: str = ""
    sunday: str = ""


class ScheduleItem(BaseModel):
    """One entry from schedules.json (source/pdf links excluded)."""

    schedule_id: str
    title: str
    published_at: str = ""


class VerificationInfo(BaseModel):
    """DVC ward verification block from profile.yaml (Phase 6 audit trail)."""

    dvc_ward_code: str = ""
    dvc_ward_name: str = ""
    dvc_ward_uuid: str = ""
    dvc_ward_state: str = ""
    dvc_checked_at: str = ""
    tthc_ward_filter: str = ""


class ProfileResponse(BaseModel):
    locality: LocalityBrief
    contact: ContactInfo = Field(default_factory=ContactInfo)
    working_hours: WorkingHours = Field(default_factory=WorkingHours)
    schedules: List[ScheduleItem] = Field(default_factory=list)
    verification: Optional[VerificationInfo] = None


class ProcedureListItem(BaseModel):
    """Whitelisted procedure fields — source_url/raw path/text never leave."""

    procedure_id: str
    name: str
    agency: str = ""
    level: str = ""
    locality_code: str = ""
    description: str = ""
    required_documents: List[str] = Field(default_factory=list)
    processing_time: str = ""
    fee: str = ""
    legal_basis: List[str] = Field(default_factory=list)


class ProcedureListResponse(BaseModel):
    items: List[ProcedureListItem] = Field(default_factory=list)
    total: int
    locality_code: str
    q: Optional[str] = None
    limit: int
    offset: int


class LegalDocumentListItem(BaseModel):
    """Manifest entry trimmed to display fields (no pdf/source URL)."""

    doc_id: str
    title: str = ""
    doc_number: str = ""
    doc_type: str = ""
    issuer: str = ""
    issued_date: str = ""
    effective_date: str = ""
    ocr_status: str = ""
    doc_scope: str = "local"
    citation_label: str = ""


class LegalDocumentListResponse(BaseModel):
    items: List[LegalDocumentListItem] = Field(default_factory=list)
    total: int
    locality_code: str
    q: Optional[str] = None
    limit: int
    offset: int
