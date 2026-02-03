# CRM Backend (MVP)

Minimal FastAPI backend with Postgres via Docker Compose.

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

Add a website snapshot:

```bash
curl -X POST http://localhost:8000/api/v1/leads/{lead_id}/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "raw_text": "Example homepage text",
    "fetched_at": "2026-02-03T12:00:00Z"
  }'
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
