# multi-orche-ai-chat

Ollama 기반 로컬 멀티모델 채팅/오케스트레이션 데스크톱 워크벤치 MVP.

## 현재 구현된 수직 슬라이스 (MVP 1차)

- 프로젝트 생성/조회/삭제(soft delete)
- 프로젝트별 채팅 생성/선택/삭제
- 채팅 메시지 타임라인 조회
- 오케스트레이터 OFF 기준 실사용 채팅 실행
  - 선택 모델 1개 이상 실행
  - `independent | chained | ordered` 모드
  - assistant 응답 DB 저장 (`model_name`, `model_role` 포함)
- 파일 업로드 + 프로젝트/채팅 경로 저장 + asset metadata DB 기록
- 모델 Sync/Pull/Toggle/Sort (우측 패널과 API 연결)
- 상단 하드웨어 메트릭 polling
- 오케스트레이터 ON 시 rule-based orchestration 실행 (planner/context_resolver/model_router/final_responder)

## 폴더 구조

- `apps/api`: FastAPI + SQLAlchemy + Alembic
- `apps/desktop`: React + Vite + Zustand + TanStack Query
- `infrastructure/compose`: PostgreSQL/Qdrant
- `infrastructure/env/.env.example`: 환경 변수 예시

## 실행 방법

### 1) 환경 변수

```bash
cp infrastructure/env/.env.example .env
```

### 2) 인프라 실행

```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d
```

### 3) API 실행

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

### 4) Desktop UI 실행

```bash
cd apps/desktop
npm install
npm run dev
```

## 핵심 API

- `POST /projects`, `GET /projects`
- `POST /chats`, `GET /chats?project_id=...`, `DELETE /chats/{id}`
- `GET /messages?chat_thread_id=...`
- `POST /messages/execute` (실제 채팅 실행)
- `GET /messages/stream?...` (SSE 단일 모델 스트림)
- `POST /assets/upload`, `GET /assets/chat/{chat_id}`
- `POST /models/sync`, `POST /models/pull`, `PATCH /models/{id}/toggle`, `PATCH /models/{id}/sort`
- `POST /orchestration/run` (실제 step 실행 + 최종 메시지 저장)
- `GET /orchestration/runs/{id}` (step intermediate + final message 포함)
- `GET /orchestration/runs/{id}/stream` (run/step 이벤트)

## 테스트

```bash
cd apps/api
pytest -q
```

## 참고

- 개발 모드(`MOAC_ENV=dev`)에서만 `MOAC_AUTO_CREATE_TABLES=true`일 때 자동 테이블 생성이 동작한다.
- 운영/배포에서는 Alembic migration을 기준으로 스키마를 관리한다.
