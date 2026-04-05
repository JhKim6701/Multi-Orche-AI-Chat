# multi-orche-ai-chat

Desktop-first local AI orchestration workbench for Ollama.

## Monorepo layout

- `apps/api`: FastAPI + SQLAlchemy + Alembic + LangGraph-ready orchestration skeleton
- `apps/desktop`: React + TypeScript + Vite UI (3 panel layout)
- `packages/*`: shared placeholders for future extraction
- `infrastructure/compose`: Docker Compose for PostgreSQL + Qdrant
- `docs/*`: architecture, ADRs, API, runbook

## Quick start

1. Copy env file:
   ```bash
   cp infrastructure/env/.env.example .env
   ```
2. Start infra:
   ```bash
   docker compose -f infrastructure/compose/docker-compose.yml up -d
   ```
3. Run API:
   ```bash
   cd apps/api
   pip install -e .
   uvicorn app.main:app --reload --port 8000
   ```
4. Run desktop UI:
   ```bash
   cd apps/desktop
   npm install
   npm run dev
   ```

## Tests

```bash
cd apps/api
pytest
```

## Implemented MVP

- Project/Chat/Message/Asset/ModelRegistry/Orchestration DB schema
- Project/Chat CRUD + message creation/listing
- Ollama client abstraction + model sync/pull/delete/toggle endpoints
- Asset upload with filename sanitization and path traversal protection
- Hardware metrics endpoint with graceful GPU fallback
- Basic orchestration run+step persistence and event stream placeholder
- React desktop-first 3-panel skeleton with top hardware bar and model panel

