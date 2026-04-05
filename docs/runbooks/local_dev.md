# Local Development Runbook

1. `cp infrastructure/env/.env.example .env`
2. `docker compose -f infrastructure/compose/docker-compose.yml up -d`
3. `cd apps/api && uvicorn app.main:app --reload`
4. `cd apps/desktop && npm run dev`
5. (Tauri desktop) `cd apps/desktop && npm run tauri:dev`
6. (Tauri build) `cd apps/desktop && npm run build && npm run tauri:build`
