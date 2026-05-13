from __future__ import annotations

from pydantic import BaseModel


class GmailConnectUrlResponse(BaseModel):
    """Plain string so JSON always includes a navigable URL for the browser."""
    connect_url: str


class SendAsAlias(BaseModel):
    send_as_email: str
    display_name: str | None = None
    is_default: bool = False
    is_primary: bool = False
    verification_status: str | None = None


class GmailSendAsAliasesResponse(BaseModel):
    aliases: list[SendAsAlias]


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
