from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lead import LeadRead


class ProspectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    source: str
    external_id: str | None = None
    company_name: str
    category: str | None = None
    address: str
    phone: str | None = None
    website_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    raw_source_payload: dict[str, object]
    import_status: str
    created_at: datetime
    updated_at: datetime


class ProspectListResponse(BaseModel):
    items: list[ProspectRead]
    total: int
    offset: int
    limit: int


class ProspectImportItem(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    external_id: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    website_url: str | None = Field(default=None, max_length=500)
    rating: float | None = None
    review_count: int | None = None
    raw_source_payload: dict[str, object] | None = None
    import_status: str | None = Field(default=None, max_length=20)


class ProspectImportRequest(BaseModel):
    items: list[ProspectImportItem] = Field(min_length=1, max_length=5000)


class ProspectImportSkipped(BaseModel):
    row_index: int
    reason: str
    source: str | None = None
    external_id: str | None = None
    company_name: str | None = None
    address: str | None = None


class ProspectImportError(BaseModel):
    row_index: int
    reason: str
    source: str | None = None
    external_id: str | None = None
    company_name: str | None = None
    address: str | None = None


class ProspectImportResponse(BaseModel):
    total_received: int
    imported_count: int
    skipped_count: int
    error_count: int
    imported: list[ProspectRead]
    skipped: list[ProspectImportSkipped]
    errors: list[ProspectImportError]


class LocationSuggestionItem(BaseModel):
    description: str
    place_id: str


class LocationSuggestionsResponse(BaseModel):
    suggestions: list[LocationSuggestionItem]


class ProspectRunSearchRequest(BaseModel):
    location: str = Field(min_length=1)
    radius: int = Field(default=15000, ge=1, le=50000)
    categories: list[str] = Field(min_length=1, max_length=64)
    keyword: str = Field(default="business", min_length=1, max_length=100)
    missing_website_only: bool = False
    limit: int = Field(default=300, ge=1, le=5000)


class ProspectRunSearchResponse(BaseModel):
    fetched_count: int
    import_result: ProspectImportResponse


class ProspectConvertRequest(BaseModel):
    prospect_ids: list[UUID] = Field(min_length=1, max_length=5000)
    require_website: bool = False


class ProspectConvertSkipped(BaseModel):
    prospect_id: UUID
    reason: str
    company_name: str
    address: str
    website_url: str | None = None


class ProspectConvertResponse(BaseModel):
    requested_count: int
    found_count: int
    converted_count: int
    skipped_count: int
    converted_leads: list[LeadRead]
    skipped: list[ProspectConvertSkipped]


class ProspectBulkDeleteRequest(BaseModel):
    prospect_ids: list[UUID] = Field(min_length=1, max_length=500)


class ProspectBulkDeleteResponse(BaseModel):
    deleted_count: int
