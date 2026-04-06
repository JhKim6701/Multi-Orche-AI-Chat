# Local Development Runbook

1. `cp infrastructure/env/.env.example .env`
2. `docker compose -f infrastructure/compose/docker-compose.yml up -d`
3. `cd apps/api && uvicorn app.main:app --reload --port 8000`
4. 웹 모드: `cd apps/desktop && npm run dev`
5. 데스크톱 모드 권장 env: `MOAC_ENV=desktop` (data root 자동 `~/.multi-orche-ai-chat/data`)
6. 데스크톱 실행 전 점검: `cd apps/desktop && npm run doctor`
7. Tauri desktop(dev): `cd apps/desktop && npm run tauri:dev` 또는 `npm run dev:desktop`
8. Tauri build: `cd apps/desktop && npm run build:desktop`
