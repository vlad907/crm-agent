# CRM Backend (MVP)

Minimal FastAPI backend with Postgres via Docker Compose.

Set `OPENAI_API_KEY` in your environment (or `.env`) before using `run-agent1`.

## Run

```bash
docker compose up --build
```

## Migrations

```bash
docker compose exec backend alembic upgrade head
```

## Health Check

```bash
curl http://localhost:8000/health
```

## API Examples

Create a lead:

```bash
curl -X POST http://localhost:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ada Lovelace",
    "title": "CTO",
    "company": "Analytical Engines",
    "industry": "Software",
    "location": "London",
    "website_url": "https://example.com",
    "email": "ada@example.com",
    "source": "import",
    "status": "new"
  }'
```

List leads:

```bash
curl "http://localhost:8000/api/v1/leads?status=new&q=Engine&limit=20&offset=0"
```

Ingest a website into `WebsiteSnapshot`:

```bash
# 1) Create a lead with a website URL and capture its id
LEAD_ID=$(curl -s -X POST http://localhost:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ada Lovelace",
    "title": "CTO",
    "company": "Analytical Engines",
    "industry": "Software",
    "location": "London",
    "website_url": "https://example.com",
    "email": "ada@example.com",
    "source": "import",
    "status": "new"
  }' | jq -r '.id')

# 2) Ingest website content for the lead
curl -X POST "http://localhost:8000/api/v1/leads/${LEAD_ID}/ingest-website"

# 3) List snapshots stored for that lead
curl "http://localhost:8000/api/v1/leads/${LEAD_ID}/snapshots"

# 4) Run Agent 1 on the latest snapshot and persist output to email_drafts.agent1_output
curl -X POST "http://localhost:8000/api/v1/leads/${LEAD_ID}/run-agent1"

# 5) Run Agent 2 to generate subject/email draft
curl -X POST "http://localhost:8000/api/v1/leads/${LEAD_ID}/run-agent2"

# 6) Run Agent 3 verifier (updates latest draft with decision + final_email)
curl -X POST "http://localhost:8000/api/v1/leads/${LEAD_ID}/run-agent3"

# 7) Get latest snapshot + agent outputs + latest verifier context
curl "http://localhost:8000/api/v1/leads/${LEAD_ID}/latest-context"
```

Create an email draft:

```bash
curl -X POST http://localhost:8000/api/v1/leads/{lead_id}/drafts \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Quick intro",
    "body": "Hi there, wanted to reach out...",
    "decision": "draft",
    "agent1_output": {"score": 0.82},
    "agent3_verdict": {"approved": true}
  }'
```
## Easy Command to test entire backend
```bash 
BASE="http://localhost:8000"

LEAD_ID=$(curl -s -X POST "$BASE/api/v1/leads" \
  -H "Content-Type: application/json" \
  -d '{"name":"Stoble Coffee","title":"Owner","company":"Stoble Coffee","industry":"Hospitality","location":"Chico, CA","website_url":"https://stoblecoffee.com/","email":"contact@stoblecoffee.com","source":"manual","status":"new"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "LEAD_ID=$LEAD_ID"

echo "== ingest-website =="
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/ingest-website" | python3 -m json.tool

echo "== run-agent1 =="
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent1" | python3 -m json.tool

echo "== run-agent2 =="
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent2" | python3 -m json.tool

echo "== run-agent3 =="
curl -s -X POST "$BASE/api/v1/leads/$LEAD_ID/run-agent3" | python3 -m json.tool

echo "== latest-context =="
curl -s "$BASE/api/v1/leads/$LEAD_ID/latest-context" | python3 -m json.tool
```