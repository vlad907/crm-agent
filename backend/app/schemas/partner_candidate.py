from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PartnerStatus = Literal["new", "reviewed", "contacted", "replied", "active_partner", "ignored", "converted"]


class PartnerCandidateCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    partnership_type: str | None = Field(default=None, max_length=100)
    source: str = Field(default="crawler", max_length=100)
    status: PartnerStatus = "new"


class PartnerCandidateUpdate(BaseModel):
    status: PartnerStatus | None = None
    partnership_type: str | None = None
    recommended_outreach_angle: str | None = None
    outreach_subject: str | None = None
    outreach_body: str | None = None
    outreach_status: str | None = None


class PartnerCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    company_name: str
    website: str | None
    industry: str | None
    location: str | None
    partnership_type: str | None
    fit_score: float | None
    extracted_signals: dict[str, Any] | None
    recommended_outreach_angle: str | None
    contact_emails: list[str] | None
    contact_form_url: str | None
    source: str
    status: str
    outreach_subject: str | None = None
    outreach_body: str | None = None
    outreach_status: str | None = None
    created_at: datetime
    updated_at: datetime


class PartnerCandidateListResponse(BaseModel):
    items: list[PartnerCandidateRead]
    total: int


class PartnerDiscoveryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="Discovery intent, e.g. 'find restaurant IT vendors'")
    location: str | None = Field(default=None, max_length=255)
    max_results: int = Field(default=10, ge=1, le=50)


class PartnerSearchRequest(BaseModel):
    discovery_intent: str = Field(min_length=1, max_length=1000, description="What kind of partner/vendor/MSP you're looking for")
    max_results: int = Field(default=10, ge=3, le=20)
    min_fit_score: float = Field(default=0.0, ge=0.0, le=1.0)


class PartnerSearchProgress(BaseModel):
    total_found: int
    analyzed: int
    qualified: int
    skipped_no_website: int = 0
    skipped_duplicate: int = 0
    errors: int


class PartnerSearchResponse(BaseModel):
    progress: PartnerSearchProgress
    candidates: list[PartnerCandidateRead]


class ConvertPartnersRequest(BaseModel):
    partner_ids: list[UUID] = Field(min_length=1)
    require_website: bool = False


class ConvertPartnersSkipped(BaseModel):
    partner_id: UUID
    reason: str
    company_name: str


class ConvertPartnersResponse(BaseModel):
    requested_count: int
    found_count: int
    converted_count: int
    skipped_count: int
    skipped: list[ConvertPartnersSkipped]
