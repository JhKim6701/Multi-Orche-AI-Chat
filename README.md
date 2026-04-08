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
- 오케스트레이터 ON 시 LangGraph 기반 orchestration 그래프 실행 (planner/context_resolver/model_router/final_responder/reviewer/critic/revision/publish)
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

## 실행 방법 (Release Hardening 기준)

### 1) 환경 변수

```bash
cp infrastructure/env/.env.example .env
```

### 2) 인프라 실행

```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d
```

- 기본 런타임 우선순위는 **PostgreSQL + Qdrant + Host Ollama** 입니다.
- SQLite는 빠른 로컬 실험용 fallback이며, 단일 프로세스 dev 상황에서만 권장됩니다.

### 3) API 실행

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

### 4) Desktop UI 실행 (Web dev mode)

```bash
cd apps/desktop
npm install
npm run dev
```

### 5) Desktop mode 실행 (Tauri dev / build)

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

프로덕션 빌드(패키징):

```bash
npm run build:desktop
```

## Desktop/Web 실행 모드와 의존성

- **Web dev mode**: `MOAC_ENV=dev` + API 백엔드를 별도 프로세스로 실행한 뒤 `npm run dev`.
- **Desktop mode**: `MOAC_ENV=desktop` 권장. 기본 data root는 `~/.multi-orche-ai-chat/data`.
- 운영 전제: **Tauri 프론트는 패키징되지만 백엔드는 별도 프로세스로 항상 실행**되어야 함.
  - 즉, 데스크톱 앱만 실행해도 orchestration/RAG는 동작하지 않으며 backend + Ollama + Qdrant + DB 준비가 필요.
- 의존성 상태 해석:
  - `system/readiness`: 실행 전(preflight) 준비 여부 (`ready=true/false`)
  - `system/health`: 실행 중(runtime) 지속 상태 (`ok/degraded`)
- `npm run doctor`는 health/readiness를 함께 점검하고, backend/database/ollama/qdrant/upload_root/migration 상태와 recovery hint를 출력.

## 환경 변수 우선순위

1. **프로세스 환경 변수**(shell export / CI secret)
2. 프로젝트 루트 `.env` (`infrastructure/env/.env.example` 기반)
3. 코드 기본값(예: data root fallback)

`MOAC_ENV`, `MOAC_DATA_ROOT`, `MOAC_UPLOAD_ROOT`, `MOAC_DATABASE_URL`, `MOAC_QDRANT_URL`, `MOAC_OLLAMA_BASE_URL`를 우선 관리하세요.

## 로컬 데이터 저장 위치

- `MOAC_DATA_ROOT` (기본: dev=`./data`, desktop=`~/.multi-orche-ai-chat/data`)
- 업로드/생성 산출물: `${MOAC_UPLOAD_ROOT}` (기본 `${MOAC_DATA_ROOT}/uploads`)
- 런타임 상태: `${MOAC_DATA_ROOT}/runtime_state.json`
- 승인 대기/결정 상태는 `orchestration_runs.approval_status`, `pending_payload_json`, `approval_decided_at` DB 필드가 source of truth.

## 장애 시 점검 순서 (권장)

1. `cd apps/desktop && npm run doctor`
2. `GET /system/readiness`에서 `unresolved_dependencies` 확인
3. `GET /system/health?verbose=true`로 runtime 상세 확인(dev에서만 민감정보 노출)
4. 인프라 확인
   - backend 프로세스
   - Ollama
   - Qdrant
   - DB/Postgres
5. ChatPanel/TopBar의 degraded alert 및 recovery hint 확인 후 재시도

## Known issues / current limitations

- 현재 릴리스 후보 구조는 **Tauri 번들만으로 완결 실행되지 않으며**, backend가 별도 프로세스로 반드시 필요합니다.
- Ollama/Qdrant/DB 중 하나라도 비가용이면 orchestration 또는 retrieval 기능은 부분/전체 degraded 상태가 됩니다.
- dev 경로(`MOAC_ENV=dev`)는 단일 프로세스 실험 친화적이며, production-like 운영 경로(`MOAC_ENV=desktop` + 외부 의존성 상시 기동)와 차이가 있습니다.
- desktop doctor는 preflight를 빠르게 알려주지만, 네트워크/권한/성능 병목의 모든 원인을 자동 복구하지는 않습니다.
- UI는 release candidate 수준으로 정리되었지만, 아주 긴 타임라인/대용량 asset 상황에서 추가 UX 폴리싱 여지가 남아 있습니다.

## Release candidate 체크리스트 (packaging/ops)

1. 환경 변수 준비 (`.env`, `MOAC_*` 우선순위 확인)
2. 인프라 기동 (`postgres`, `qdrant`, `ollama`)
3. migration 적용 (`alembic upgrade head`)
4. backend 실행 (`uvicorn app.main:app --reload --port 8000`)
5. desktop preflight (`cd apps/desktop && npm run doctor`)
6. 실행 경로 선택
   - web dev: `npm run dev`
   - tauri dev: `npm run tauri:dev`
   - build: `npm run build:desktop`
7. 장애 시 복구 순서 적용 (readiness → health → dependency restart)

## Merge / Release decision flow

1. **지금 실행 가능한가?**
   - doctor + readiness/health 확인
2. **데모 가능한가?**
   - 아래 “Demo 최소 성공 시나리오”를 끝까지 수행
3. **merge해도 되는가?**
   - blocker 없는지 확인, 남은 항목은 backlog(Next/Later)로 분류
4. **production blocker는 무엇인가?**
   - Known issues + roadmap 문서에서 확인

관련 문서:
- Runbook: `docs/runbooks/local_dev.md`
- Backlog/Roadmap: `docs/roadmaps/release-candidate-backlog.md`

## Demo 최소 성공 시나리오

1. `npm run doctor`에서 readiness가 `ready`인지 확인
2. Project 생성
3. Chat 생성
4. Manual execution 1회 수행
5. Orchestration run 생성 (`require_approval_before_publish=true`)
6. Run detail에서 `approval_pending` 확인
7. Approve 또는 Reject 수행 후 최종 상태 확인

## 테스트와 release 판단 연결

- `tests/test_release_smoke.py`: core API smoke gate(project/chat/manual/orchestration/approval/role-pref)
- `GET /system/health`, `GET /system/readiness`: runtime/preflight gate
- `npm run doctor`: desktop preflight gate
- desktop UI regression(components tests): 상태 배지/알림/drawer 렌더링 회귀 확인

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
