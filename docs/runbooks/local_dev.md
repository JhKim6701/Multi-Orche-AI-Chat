# Local Development Runbook (Release-Hardening)

## 1) 공통 사전 준비

1. `cp infrastructure/env/.env.example .env`
2. `docker compose -f infrastructure/compose/docker-compose.yml up -d`
3. `cd apps/api && uvicorn app.main:app --reload --port 8000`

## 2) Web dev mode

1. `cd apps/desktop`
2. `npm install`
3. `npm run dev`

## 3) Desktop mode (Tauri)

1. 권장: `export MOAC_ENV=desktop`
2. `cd apps/desktop`
3. `npm install`
4. `npm run doctor` (preflight 점검)
5. `npm run tauri:dev` (또는 `npm run dev:desktop`)

## 4) Desktop 패키징/배포 전제

- `npm run build:desktop`는 프론트/Tauri 번들을 생성.
- **중요**: 번들만으로 backend/orchestration은 동작하지 않음.
- 운영 시 반드시 별도 backend 프로세스 + Ollama + Qdrant + DB를 함께 관리.

## 5) 환경 변수 우선순위

1. 프로세스 환경 변수
2. `.env`
3. 코드 기본값

핵심 변수: `MOAC_ENV`, `MOAC_DATA_ROOT`, `MOAC_UPLOAD_ROOT`, `MOAC_DATABASE_URL`, `MOAC_QDRANT_URL`, `MOAC_OLLAMA_BASE_URL`

## 6) 데이터 저장 위치

- dev 기본: `./data`
- desktop 기본: `~/.multi-orche-ai-chat/data`
- upload/artifact: `${MOAC_UPLOAD_ROOT}` (기본 `${MOAC_DATA_ROOT}/uploads`)
- runtime state: `${MOAC_DATA_ROOT}/runtime_state.json`

## 7) 장애 대응 순서

1. `npm run doctor`
2. `/system/readiness` 확인 (실행 전 준비 상태)
3. `/system/health` 확인 (실행 중 상태)
4. unresolved dependency 순서대로 복구 (backend → DB → Ollama → Qdrant)
5. UI(TopBar/ChatPanel)에서 recovery hint 확인 후 재시도
