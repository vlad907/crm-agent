# CRM Command

A desktop CRM and AI outreach assistant. Find local businesses and partnership
candidates, let AI research each one, draft and review emails, then send them
through your own Gmail account — all from a single Mac/Windows/Linux app.

Built on FastAPI + Next.js + Electron. Backend, frontend, and Python venv
are bundled into a single installable application.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [Install (end users)](#install-end-users)
3. [First-time setup](#first-time-setup)
4. [Using the app](#using-the-app)
5. [Build from source](#build-from-source)
6. [Publish a new release](#publish-a-new-release)
7. [Developer notes](#developer-notes)

---

## What it does

- **Discovery** — find local businesses via Google Places, or partnership/vendor
  candidates via web search, all from inside the app.
- **AI research** — each lead is automatically researched: the AI scrapes the
  company's website, extracts pain points, and identifies hooks for outreach.
- **Draft & verify** — Agent 2 writes a personalized email, Agent 3 verifies it
  against your tone/guardrails. Drafts you approve become Gmail drafts you can
  send with one click.
- **Inbox & threads** — incoming replies are pulled into the app, classified,
  and given an AI-suggested response that you can review and send.
- **Partnerships** — separate flow for finding vendor/subcontractor networks
  where the goal is to get added to *their* dispatch list (not to sell to them).

All data stays local in a SQLite file inside your user data directory; nothing
syncs anywhere unless you explicitly connect Gmail.

---

## Install (end users)

The latest installer is committed to the `main` branch of this repo using
**Git LFS** (the DMG is ~171 MB). You need Git LFS installed locally to clone
it correctly:

```bash
# one-time install
brew install git-lfs        # macOS
# OR: sudo apt install git-lfs
# OR: download from https://git-lfs.com
git lfs install

# clone with the installer files
git clone git@github.com:vlad907/crm-agent.git
cd crm-agent/frontend/electron-dist
```

If you've already cloned the repo without LFS, run `git lfs pull` from inside
the repo to fetch the binary files.

### macOS

1. Open `CRM Command-<version>-arm64.dmg`.
2. Drag **CRM Command** into your `Applications` folder.
3. First launch: macOS will block the app because it isn't notarized.
   Right-click the app → **Open** → **Open** in the dialog.
   (You only have to do this once.)

The app stores its database at
`~/Library/Application Support/crm-frontend/crm.db`.

### Windows

1. Run `CRM Command-<version>-Setup.exe`.
2. Windows SmartScreen may warn about the unsigned binary — click **More info
   → Run anyway**.

### Linux

1. `chmod +x CRM\ Command-<version>.AppImage`
2. Run it.

---

## First-time setup

Open the app. You'll be walked through onboarding:

1. **Login / Workspace** — pick an email; a local workspace is created for you.
2. **API keys** — paste your own keys; they're stored encrypted-at-rest in your
   local SQLite, never sent anywhere except to the respective provider:
   - **Anthropic API key** (recommended for email generation — better
     instruction-following). Get one at console.anthropic.com.
   - **OpenAI API key** (used as fallback if no Anthropic key, and for research
     agents). Get one at platform.openai.com.
   - **Google Places API key** (for local-business discovery). Enable both
     **Places API** and **Geocoding API** in Google Cloud Console → APIs &
     Services → Library.
3. **Gmail connection** (optional but recommended) — click **Connect Gmail** to
   grant the app permission to create drafts and send on your behalf. You'll
   need a **Google OAuth client ID + secret** of your own (free; created in
   Google Cloud Console → Credentials → OAuth 2.0 Client IDs).
4. **Business profile** — name, service area, specialties, tone. This is the
   data the AI uses to personalize every email it writes for you.

Done. You can revisit any of these later under **Settings**.

---

## Using the app

### Find leads

- **Local Businesses** — Discovery → Local Businesses → enter a location, radius,
  and category (e.g. *plumbers in Chico, CA, 25 mi*). Select what you want and
  click **Import as leads**.
- **Partnership candidates** — Discovery → Partnerships → describe the kind of
  partner you want (e.g. *national MSPs that dispatch on-site IT technicians*).
  The AI ranks each company by fit score.

### Run the pipeline

From the **Leads** page:

- Click a row → side panel shows summary, AI research, and current draft.
- Select rows in bulk → **Run Full Pipeline** to research + draft for everything
  that's incomplete.
- **Re-run Pipeline (Unapproved)** forces a fresh research+draft cycle on
  anything that wasn't yet approved.

### Review and send

- Approved drafts get pushed to your Gmail Drafts folder.
- Click **Send** in the app to dispatch immediately, or open Gmail and send
  from there.
- Use the **Archive** view to see converted/sent/archived leads.

### Watch inbox

- The app syncs your Gmail inbox in the background.
- New replies appear under **Inbox** with an AI classification
  (interested, objection, question, etc.) and a suggested response you can
  approve, edit, or discard.

---

## Build from source

You'll need:

- **Node 20+** and **npm**
- **Python 3.11+**
- macOS / Linux: nothing else
- Windows: build tools (`windows-build-tools` or the VS C++ workload)

```bash
git clone git@github.com:vlad907/crm-agent.git
cd crm-agent
```

### Backend venv (one-time)

The Electron build bundles whatever venv lives at `backend/.venv`. Create it:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

### Frontend dependencies

```bash
cd frontend
npm install
```

### Run in dev mode (hot reload)

In one terminal:

```bash
docker compose up backend       # or run uvicorn directly
```

In another:

```bash
cd frontend
npm run electron:dev
```

The Electron window opens, the renderer hot-reloads, and requests are proxied
to the backend on `:8000`.

### Build the desktop app

```bash
cd frontend
npm run electron:build
```

Output is dropped in `frontend/electron-dist/`:

- `CRM Command-<version>-arm64.dmg`  (macOS Apple Silicon)
- `CRM Command-<version>-arm64-mac.zip`
- `CRM Command-<version>-Setup.exe`  (Windows, on a Windows host)
- `CRM Command-<version>.AppImage`   (Linux)

The build script sets `CRM_API_PROXY_TARGET=http://127.0.0.1:8765` so the
packaged app talks to its bundled backend on port 8765 (avoiding collisions
with any dev backend on 8000).

---

## Publish a new build

Builds are committed directly to `main` so anyone who clones the repo gets
the latest installer alongside the source. No GitHub release page involved.

### 1. Build the installer

```bash
cd frontend
npm run electron:build
```

Artifacts land in `frontend/electron-dist/`:

- `CRM Command-<version>-arm64.dmg`
- `CRM Command-<version>-arm64-mac.zip`
- `CRM Command-<version>.AppImage` (Linux host only)
- `CRM Command-<version>-Setup.exe` (Windows host only)

### 2. Commit the new installer to main

```bash
cd ..   # back to repo root
git add frontend/electron-dist/"CRM Command-"*.dmg \
        frontend/electron-dist/"CRM Command-"*-mac.zip \
        frontend/electron-dist/"CRM Command-"*.blockmap
git commit -m "Build v$(cd frontend && node -p 'require(\"./package.json\").version')"
git push origin main
```

That's it — users `git pull` (or re-clone) and run the new installer.

### Optional: bump the version first

```bash
cd frontend
npm version patch    # 0.1.0 → 0.1.1, or use `minor` / `major`
cd ..
git push origin main
```

### Optional: code signing for macOS

If you want to skip the Gatekeeper warning:

1. Get an **Apple Developer ID Application** certificate ($99/yr).
2. Set env vars before building:
   ```bash
   export CSC_LINK=/path/to/cert.p12
   export CSC_KEY_PASSWORD=...
   export APPLE_ID=...
   export APPLE_APP_SPECIFIC_PASSWORD=...
   export APPLE_TEAM_ID=...
   ```
3. `electron-builder` picks these up automatically and signs + notarizes.

---

## Developer notes

### Architecture

```
┌────────────────────────────────────────────────────┐
│              Electron main process                 │
│  ┌─────────────────┐    ┌──────────────────────┐  │
│  │ Next.js         │    │ FastAPI (uvicorn)    │  │
│  │ standalone      │───▶│ Python 3.11 + venv   │  │
│  │ :3000           │    │ :8765                │  │
│  └─────────────────┘    └──────────────────────┘  │
│           ▲                       │                │
│           │                       ▼                │
│      BrowserWindow         SQLite (user data dir)  │
└────────────────────────────────────────────────────┘
```

- The Electron main process (`frontend/electron/main.cjs`) spawns:
  - A Next.js standalone server on a free port (3000+) for the UI.
  - A uvicorn-hosted FastAPI app on port **8765** (different from dev port
    8000 to avoid collisions if you're also running the dev stack).
- The browser window points at the Next.js URL, and `/api/v1/*` requests are
  rewritten (at build time) to forward to the FastAPI backend.

### Multi-tenant model

All CRM data is scoped by `workspace_id`. Every request resolves identity from:

- `X-Workspace-Id` header
- `X-User-Id` header

If headers are omitted, the backend falls back to `DEFAULT_WORKSPACE_ID` /
`DEFAULT_USER_ID` env vars. In development, startup bootstrap creates a default
workspace + user if neither exists.

Tenant-scoped tables:
- `leads`, `prospects`, `partner_candidates`
- `website_snapshots`, `email_drafts`
- `email_threads`, `email_messages`
- `workspace_settings`, `workspace_profile`, `workspace_ai_strategy`
- `oauth_tokens`, `integration_accounts`

### Backend (Docker, dev mode)

```bash
docker compose up --build
docker compose exec backend alembic upgrade head
curl http://localhost:8000/health
```

### Auth (dev)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","name":"Dev User"}'
```

Returns `workspace_id` + `user_id` — paste these into `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WORKSPACE_ID=<workspace_uuid>
NEXT_PUBLIC_USER_ID=<user_uuid>
```

### Useful endpoints

| Method  | Path                                  | What it does                          |
|---------|---------------------------------------|---------------------------------------|
| GET     | `/health`                             | Liveness                              |
| POST    | `/api/v1/auth/login`                  | Dev login / create user               |
| GET     | `/api/v1/me`                          | Resolve current workspace + user      |
| GET     | `/api/v1/leads`                       | List leads (workspace-scoped)         |
| POST    | `/api/v1/leads/imports`               | Bulk import with dedupe               |
| POST    | `/api/v1/leads/{id}/run-agent1`       | Research the lead                     |
| POST    | `/api/v1/leads/{id}/run-agent2`       | Draft the email                       |
| POST    | `/api/v1/leads/{id}/run-agent3`       | Verify the draft                      |
| GET     | `/api/v1/prospects`                   | List discovery prospects              |
| POST    | `/api/v1/prospects/convert-to-leads`  | Promote prospects → leads             |
| GET     | `/api/v1/partnerships`                | List partnership candidates           |
| POST    | `/api/v1/partnerships/{id}/generate-outreach` | AI-draft vendor inquiry email |
| GET     | `/api/v1/settings`                    | Per-workspace API keys + Gmail status |
| GET     | `/api/v1/inbox/threads`               | Email threads with classifications    |

### Environment variables (backend)

```bash
DATABASE_URL=sqlite:///./crm.db          # SQLite (Electron) or Postgres
ENV=development
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
DEFAULT_WORKSPACE_ID=
DEFAULT_USER_ID=
```

Per-workspace API keys set via the Settings UI override these env vars.

---

## License

Proprietary — © Blue Arc Networks. All rights reserved.
