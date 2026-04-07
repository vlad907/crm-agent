from __future__ import annotations

from pydantic import BaseModel


class GmailConnectUrlResponse(BaseModel):
    """Plain string so JSON always includes a navigable URL for the browser."""
    connect_url: str


class GmailCallbackResponse(BaseModel):
    provider: str = "gmail"
    workspace_id: str
    connected: bool
    integration_status: str
    connected_email: str | None = None
    last_error: str | None = None


class GmailStatusResponse(BaseModel):
    provider: str = "gmail"
    workspace_id: str
    connected: bool
    connected_email: str | None = None
    integration_status: str
    last_error: str | None = None
