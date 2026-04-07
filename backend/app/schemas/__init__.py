from app.schemas.auth import DevLoginRequest, DevLoginResponse
from app.schemas.agent1 import Agent1RunResponse, LatestContextResponse, LatestContextSnapshot
from app.schemas.agent3 import Agent3RunResponse, FinalEmailRead
from app.schemas.automation_settings import WorkspaceAutomationSettingsRead, WorkspaceAutomationSettingsUpdate
from app.schemas.email_draft import DraftReviewQueueSummary, EmailDraftCreate, EmailDraftRead
from app.schemas.gmail_integration import GmailCallbackResponse, GmailConnectUrlResponse, GmailStatusResponse
from app.schemas.lead import (
    LeadCreate,
    LeadImportDuplicate,
    LeadImportError,
    LeadImportItem,
    LeadImportRequest,
    LeadImportResponse,
    LeadListResponse,
    LeadPipelineSummary,
    LeadRead,
    LeadUpdate,
)
from app.schemas.prospect import (
    LocationSuggestionItem,
    LocationSuggestionsResponse,
    ProspectConvertRequest,
    ProspectConvertResponse,
    ProspectImportRequest,
    ProspectImportResponse,
    ProspectListResponse,
    ProspectRead,
    ProspectRunSearchRequest,
    ProspectRunSearchResponse,
)
from app.schemas.settings import WorkspaceSettingsRead, WorkspaceSettingsUpdate
from app.schemas.website_page import WebsitePageRead
from app.schemas.website_snapshot import (
    WebsiteSnapshotCreate,
    WebsiteSnapshotIngestRead,
    WebsiteSnapshotRead,
)
from app.schemas.workspace_profile import WorkspaceProfileRead, WorkspaceProfileUpdate
from app.schemas.workspace_ai_strategy import WorkspaceAIStrategyRead, WorkspaceAIStrategyUpdate
from app.schemas.workspace import MeResponse, UserCreate, UserRead, WorkspaceCreate, WorkspaceRead

__all__ = [
    "DevLoginRequest",
    "DevLoginResponse",
    "Agent1RunResponse",
    "Agent3RunResponse",
    "WorkspaceAutomationSettingsRead",
    "WorkspaceAutomationSettingsUpdate",
    "EmailDraftCreate",
    "EmailDraftRead",
    "DraftReviewQueueSummary",
    "GmailConnectUrlResponse",
    "GmailCallbackResponse",
    "GmailStatusResponse",
    "FinalEmailRead",
    "LeadCreate",
    "LeadImportDuplicate",
    "LeadImportError",
    "LeadImportItem",
    "LeadImportRequest",
    "LeadImportResponse",
    "LeadListResponse",
    "LeadPipelineSummary",
    "LeadRead",
    "LeadUpdate",
    "ProspectRead",
    "ProspectListResponse",
    "ProspectImportRequest",
    "ProspectImportResponse",
    "ProspectRunSearchRequest",
    "ProspectRunSearchResponse",
    "LocationSuggestionItem",
    "LocationSuggestionsResponse",
    "ProspectConvertRequest",
    "ProspectConvertResponse",
    "WorkspaceSettingsRead",
    "WorkspaceSettingsUpdate",
    "WorkspaceProfileRead",
    "WorkspaceProfileUpdate",
    "WorkspaceAIStrategyRead",
    "WorkspaceAIStrategyUpdate",
    "LatestContextResponse",
    "LatestContextSnapshot",
    "WebsitePageRead",
    "WebsiteSnapshotCreate",
    "WebsiteSnapshotIngestRead",
    "WebsiteSnapshotRead",
    "WorkspaceCreate",
    "WorkspaceRead",
    "UserCreate",
    "UserRead",
    "MeResponse",
]
