# Local Development Runbook

1. `cp infrastructure/env/.env.example .env`
2. `docker compose -f infrastructure/compose/docker-compose.yml up -d`
3. `cd apps/api && uvicorn app.main:app --reload`
4. `cd apps/desktop && npm run dev`
