# CRM MVP

FastAPI backend + Next.js frontend.

## Multi-Tenant Model

All CRM pipeline data is tenant-scoped by `workspace_id`:
- `leads`
- `website_snapshots`
- `email_drafts`

New foundational tables:
- `workspaces`
- `users`
- `integration_accounts`
- `oauth_tokens`

Every API request resolves identity from:
- `X-Workspace-Id`
- `X-User-Id`

If headers are omitted, backend uses:
- `DEFAULT_WORKSPACE_ID`
- `DEFAULT_USER_ID`

If env defaults are missing in development, startup bootstrap creates a default workspace/user and uses them as runtime defaults.

## Environment

`.env.example` now includes:

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=crm_db
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/crm_db
ENV=development
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_RATE_LIMIT_RETRIES=5
OPENAI_RATE_LIMIT_BACKOFF_SECONDS=1.0
DEFAULT_WORKSPACE_ID=
DEFAULT_USER_ID=
```

## Backend Run

```bash
docker compose up --build
```

## Migrations

```bash
docker compose exec backend alembic upgrade head
```

## Dev Bootstrap Flow

1) Start stack and run migrations.

2) Fetch current request identity:

```bash
curl http://localhost:8000/api/v1/me
```

3) Copy returned IDs into `.env`:

```bash
DEFAULT_WORKSPACE_ID=<workspace_uuid>
DEFAULT_USER_ID=<user_uuid>
```

4) Restart backend:

```bash
docker compose up -d --build backend
```

## Health Check

```bash
curl http://localhost:8000/health
```

## Frontend Setup

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WORKSPACE_ID=<workspace_uuid>
NEXT_PUBLIC_USER_ID=<user_uuid>
```

Frontend sends `X-Workspace-Id` and `X-User-Id` on every request.
You can override IDs at runtime in `Settings` (`/settings`), which stores values in browser localStorage.
You can also use `Login` (`/login`) to sign in with email; if user does not exist yet, backend creates it and frontend stores returned workspace/user IDs.

Local frontend run:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Docker frontend run:

```bash
docker compose up --build frontend
```

## Dev Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","name":"Dev User"}'
```

## Header Usage

Use headers for explicit workspace scoping:

```bash
-H "X-Workspace-Id: <workspace_uuid>" \
-H "X-User-Id: <user_uuid>"
```

## Workspace/User Endpoints

Create workspace:

```bash
curl -X POST http://localhost:8000/api/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Workspace"}'
```

Create user in workspace (must match request workspace header):

```bash
curl -X POST http://localhost:8000/api/v1/workspaces/<workspace_uuid>/users \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" \
  -d '{"email":"owner@acme.com","name":"Owner","role":"owner"}'
```

## Pipeline Example (Scoped)

```bash
BASE="http://localhost:8000"
WORKSPACE_ID="<workspace_uuid>"
USER_ID="<user_uuid>"

LEAD_ID=$(curl -s -X POST "$BASE/api/v1/leads" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" \
  -d '{
    "name":"Ada Lovelace",
    "title":"CTO",
    "company":"Analytical Engines",
    "industry":"Software",
    "location":"London",
    "website_url":"https://example.com",
    "email":"ada@example.com",
    "source":"manual",
    "status":"new"
  }' | jq -r '.id')

# ingest website
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/ingest-website" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

# run agent1
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent1" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

# run agent2
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent2" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

# run agent3
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent3" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

# list snapshots + drafts + latest context
curl -s "$BASE/api/v1/leads/$LEAD_ID/snapshots" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

curl -s "$BASE/api/v1/leads/$LEAD_ID/drafts" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq

curl -s "$BASE/api/v1/leads/$LEAD_ID/latest-context" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-User-Id: $USER_ID" | jq
```

## Lead Import Workflow

Import leads in bulk (workspace-scoped, with dedupe + row-level errors):

```bash
curl -X POST http://localhost:8000/api/v1/leads/imports \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" \
  -d '{
    "source": "google_places",
    "items": [
      {
        "name": "Acme Plumbing",
        "company": "Acme Plumbing",
        "industry": "plumber",
        "location": "Chico, CA",
        "website_url": "https://acmeplumbing.example",
        "source": "google_places"
      }
    ],
    "dedupe_by_website": true,
    "dedupe_by_company_location": true
  }'
```

`crawler.py` now outputs a **prospects** import payload (for `/api/v1/prospects/import`), not direct CRM lead imports.

## Prospect Discovery Flow

Prospects are stored separately from CRM leads:

`crawler/search -> prospects -> manual review -> convert selected -> leads -> pipeline`

List prospects:

```bash
curl -s "http://localhost:8000/api/v1/prospects?limit=20&offset=0" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" | jq
```

Import prospects from crawler JSON:

```bash
curl -s -X POST http://localhost:8000/api/v1/prospects/import \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" \
  --data-binary @crawler_output.json | jq
```

Convert prospects to CRM leads:

```bash
curl -s -X POST http://localhost:8000/api/v1/prospects/convert-to-leads \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" \
  -d '{"prospect_ids":["<prospect_uuid_1>","<prospect_uuid_2>"]}' | jq
```

Workspace settings API (per-workspace API keys):

```bash
curl -s http://localhost:8000/api/v1/settings \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" | jq

curl -s -X PATCH http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace_uuid>" \
  -H "X-User-Id: <user_uuid>" \
  -d '{"google_places_api_key":"AIza...","openai_api_key":"sk-..."}' | jq
```
