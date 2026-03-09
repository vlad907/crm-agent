from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebsitePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    lead_id: UUID
    url: str = Field(min_length=1, max_length=500)
    page_type: str = Field(min_length=1, max_length=20)
    raw_text: str
    extracted_emails: list[str]
    extracted_phones: list[str]
    created_at: datetime
