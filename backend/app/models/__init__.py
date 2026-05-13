# Import all models so SQLAlchemy's metadata is fully populated before create_all().
from app.models.email_draft import EmailDraft  # noqa: F401
from app.models.email_message import EmailMessageRecord  # noqa: F401
from app.models.email_thread import EmailThread  # noqa: F401
from app.models.integration_account import IntegrationAccount  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.oauth_token import OAuthToken  # noqa: F401
from app.models.partner_candidate import PartnerCandidate  # noqa: F401
from app.models.prospect import Prospect  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.website_page import WebsitePage  # noqa: F401
from app.models.website_snapshot import WebsiteSnapshot  # noqa: F401
from app.models.workspace import Workspace  # noqa: F401
from app.models.workspace_ai_strategy import WorkspaceAIStrategy  # noqa: F401
from app.models.workspace_automation_setting import WorkspaceAutomationSetting  # noqa: F401
from app.models.workspace_profile import WorkspaceProfile  # noqa: F401
from app.models.workspace_setting import WorkspaceSetting  # noqa: F401
