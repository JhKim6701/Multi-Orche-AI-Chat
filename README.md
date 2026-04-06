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
- 자산 ingest(텍스트 추출/청크) + retrieval snippet 기반 프롬프트 컨텍스트 반영
- 모델 Sync/Pull/Toggle/Sort (우측 패널과 API 연결)
- 상단 하드웨어 메트릭 polling
- 오케스트레이터 ON 시 rule-based orchestration 실행 (planner/context_resolver/model_router/final_responder)
- topic-aware segmentation: 주제 전환 시 새 segment 자동 분리 + 관련 segment 중심 문맥 스코핑
- 이미지 업로드 시 vision-capable 모델 대상으로 실제 image payload 전달(multimodal)
- assistant 응답의 AI generated artifact(.md/.txt/.json/.py/.ts) 자동 생성 및 다운로드
- 오케스트레이션 visual drawer 패널(역할/모델/순서/reviewer/revision/provenance) 표시
- TopBar에서 GPU usage/memory + GPU routing 토글 표시

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

### 5) Tauri Desktop 실행 (개발/빌드)

Tauri prerequisite(Rust toolchain, OS별 WebView/runtime)가 준비된 환경에서:

```bash
cd apps/desktop
npm install
npm run doctor
npm run tauri:dev
```

웹 dev 서버와 Tauri를 함께 올리려면:

```bash
npm run tauri:dev:with-web
```

프로덕션 빌드:

```bash
npm run build:desktop
```

## Desktop/Web 실행 모드와 의존성

- **Web 모드**: `MOAC_ENV=dev` + API를 별도로 실행한 뒤 `npm run dev`.
- **Desktop 모드**: `MOAC_ENV=desktop` 권장. 기본 data root는 `~/.multi-orche-ai-chat/data`로 고정되어 OS별 사용자 홈 경로에 저장됨.
- 현재 구조는 **Tauri 프론트 패키징 + 백엔드 별도 로컬 서비스 실행** 방식을 사용.
- 선행 의존성:
  - API 서버 (`uvicorn app.main:app`)
  - Ollama (`MOAC_OLLAMA_BASE_URL`)
  - Qdrant (`MOAC_QDRANT_URL`)
- `npm run doctor`로 desktop 실행 전 `/system/health` + `/system/readiness` 의존성 점검 가능.

## 로컬 데이터 저장 위치

- `MOAC_DATA_ROOT` (기본: dev=`./data`, desktop=`~/.multi-orche-ai-chat/data`)
- 업로드/생성 산출물: `${MOAC_UPLOAD_ROOT}` (기본 `${MOAC_DATA_ROOT}/uploads`)
- 런타임 상태: `${MOAC_DATA_ROOT}/runtime_state.json`
- 승인 대기 상태: `${MOAC_DATA_ROOT}/pending_approvals.json`

## 핵심 API

- `POST /projects`, `GET /projects`
- `POST /chats`, `GET /chats?project_id=...`, `DELETE /chats/{id}`
- `GET /messages?chat_thread_id=...`
- `POST /messages/execute` (실제 채팅 실행)
- `GET /messages/stream?...` (SSE 단일 모델 스트림)
- `POST /assets/upload`, `GET /assets/chat/{chat_id}` (ingest status/preview 포함)
- `POST /models/sync`, `POST /models/pull`, `PATCH /models/{id}/toggle`, `PATCH /models/{id}/sort`
- `POST /orchestration/run` (실제 step 실행 + 최종 메시지 저장)
- `GET /segments?chat_thread_id=...`, `POST /segments/detect`, `POST /segments/switch`, `POST /segments/branch`
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
