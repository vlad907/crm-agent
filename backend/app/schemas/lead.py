from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LeadBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    source: str = Field(min_length=1, max_length=100)
    status: str = Field(default="new", min_length=1, max_length=50)


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    source: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=50)


class LeadRead(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    offset: int
    limit: int


class LeadImportItem(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)


class LeadImportRequest(BaseModel):
    source: str = Field(default="crawler", min_length=1, max_length=100)
    items: list[LeadImportItem] = Field(min_length=1, max_length=5000)
    dedupe_by_website: bool = True
    dedupe_by_company_location: bool = True


class LeadImportDuplicate(BaseModel):
    row_index: int = Field(ge=0)
    reason: str
    company: str | None = None
    location: str | None = None
    website_url: str | None = None


class LeadImportError(BaseModel):
    row_index: int = Field(ge=0)
    reason: str
    company: str | None = None
    location: str | None = None
    website_url: str | None = None


class LeadImportResponse(BaseModel):
    source: str
    total_received: int
    imported_count: int
    duplicate_count: int
    error_count: int
    imported: list[LeadRead]
    duplicates: list[LeadImportDuplicate]
    errors: list[LeadImportError]
