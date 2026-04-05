# multi-orche-ai-chat Codex 전용 초정밀 개발 프롬프트

## 부제
Ollama 기반 로컬 멀티모델 오케스트레이션 데스크톱 앱 구현용

## 문서 목적
이 문서는 `multi-orche-ai-chat` 프로젝트를 실제로 구현시키기 위한 **Codex 전용 초정밀 한국어 프롬프트**입니다.  
단순 아이디어 정리가 아니라, **저장소 분석 → 설계 고정 → 코드 생성 → 실행 가능한 상태 유지 → 단계별 확장**까지 유도하도록 설계했습니다.

---

## 사용 방법
이 문서는 Codex/개발형 AI 에이전트에게 그대로 전달할 수 있도록 작성된 한국어 프롬프트입니다.

권장 사용 순서:
1. 빈 저장소 또는 초기 저장소에 본문 전체를 그대로 입력합니다.
2. Codex가 저장소를 스캔한 뒤 바로 Milestone 1부터 구현하도록 둡니다.
3. 중간에 끊겼다면, 마지막 상태를 유지한 채 “현재 저장소 기준으로 계속 구현”이라고 이어서 지시합니다.
4. 특정 영역만 강화하고 싶으면 후속 제어 프롬프트를 별도로 사용합니다.

추천 후속 한 줄 지시 예시:
- 현재 저장소 기준으로 Milestone 2를 이어서 구현해라.
- 오케스트레이션 서브시스템만 집중적으로 완성해라.
- UI/UX 완성도를 높이고 작은 버튼/리사이즈/스크롤 품질을 다듬어라.
- 테스트와 문서화를 보강해라.

---

## 메인 프롬프트

```text
당신은 단순 조언자가 아니라 이 저장소의 **주 구현자(Primary Implementer)** 다.
목표는 아이디어 정리가 아니라, 실제로 실행 가능한 코드를 설계·구현·연결·검증하여 `multi-orche-ai-chat`를 완성하는 것이다.

중요 원칙:
- 추상적 브레인스토밍보다 **동작하는 코드와 실행 가능한 구조**를 우선한다.
- 핵심 경로에서 의사코드로 멈추지 말고 실제 구현을 작성한다.
- 넓은 범위의 확인 질문은 하지 말고, 진짜 진행 불가한 블로커가 있을 때만 짧게 질문한다.
- 합리적인 시니어 엔지니어 판단으로 결정하고 전진한다.
- 각 주요 단계가 끝날 때마다 **빌드 가능한 상태**를 유지한다.
- 이미 있는 코드가 있으면 먼저 읽고, 불필요한 전면 재작성은 금지한다.
- 답변은 장황한 설명보다 **결정 요약 + 파일 단위 변경 + 실행 방법** 중심으로 작성한다.
- 코드 식별자, 파일명, API 경로, DB 컬럼명은 영어로 작성한다.
- 사용자 노출 문구, README, 운영 문서, UI 텍스트는 한국어를 기본으로 한다.

======================================================================
1. 제품 목표
======================================================================

`multi-orche-ai-chat`는 일반 채팅 앱이 아니라 **로컬 우선(local-first) 멀티모델 AI 오케스트레이션 워크벤치**다.

핵심 목표:
1. 사용자가 Ollama를 통해 로컬 AI 모델을 검색/다운로드/선택할 수 있어야 한다.
2. 프로젝트 단위로 대화와 자료를 관리해야 한다.
3. 텍스트, 이미지, 일반 파일 업로드를 지원해야 한다.
4. 업로드 자료와 대화 이력을 기반으로 AI가 답할 수 있어야 한다.
5. 오케스트레이터 ON 시:
   - 사용자 요청 분석
   - 역할 분해
   - 적절한 모델/에이전트 선택
   - 실행 순서 및 병렬성 제어
   - 중간 결과 병합
   - 재시도/비평/검토
   - 필요 시 사용자 승인 요청
   - 최종 응답 생성
   를 담당해야 한다.
6. 오케스트레이터 OFF 시:
   - 사용자가 직접 선택한 여러 모델이 설정된 순서대로 응답해야 한다.
   - 독립 응답 모드와 체인 응답 모드를 지원해야 한다.
7. 상단에는 CPU/GPU/Memory/Disk 실시간 상태가 보여야 한다.
8. UI는 데스크톱 우선 3패널 구조이며, 크기 조절·스크롤·반응형이 적용되어야 한다.

======================================================================
2. 비기능/기술 방향 - 고정
======================================================================

다음 기술 방향을 기본값으로 사용하라. 충돌이나 치명적 제약이 없는 한 바꾸지 마라.

데스크톱 셸:
- Tauri v2

프론트엔드:
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Zustand
- TanStack Query
- react-router
- react-resizable-panels
- markdown renderer
- drag and drop 정렬 UI
- streaming-friendly chat UI

백엔드:
- Python 3.12+
- FastAPI
- LangGraph
- Pydantic v2
- SQLAlchemy
- Alembic

저장소:
- PostgreSQL
- Qdrant
- 로컬 파일시스템

모델 런타임:
- Ollama는 기본적으로 **호스트 OS에 네이티브 설치**
- 앱은 로컬 API를 통해 Ollama와 통신
- 추후 다른 provider 확장을 고려해 provider adapter 계층을 둔다

개발/운영:
- Docker Compose로 backend infra 구성
- Tauri로 desktop packaging
- 기본 실행 모드는 hybrid:
  - Ollama = host native
  - backend = local process 또는 docker compose
  - desktop app = local backend 연결

======================================================================
3. 아키텍처 원칙
======================================================================

반드시 다음 원칙을 따른다.

1. 모놀리식 난개발 금지
   - UI, API, orchestration, asset pipeline, retrieval, model registry, hardware monitor를 분리한다.

2. 확장 가능한 추상화 유지
   - Ollama 전용 하드코딩을 최소화하고 provider adapter 형태로 감싼다.

3. 실행 경로 우선
   - 설계 문서보다 먼저 최소 동작 경로를 만든다.
   - 단, 폴더 구조와 경계(boundary)는 처음부터 명확히 한다.

4. 오케스트레이션이 중심
   - 단순 채팅 기능보다 orchestration graph / role routing / step event / review loop를 핵심 1급 기능으로 취급한다.

5. 로컬 자원 친화적
   - 파일 저장, 하드웨어 모니터링, GPU 토글, host Ollama 연결이 자연스럽게 동작해야 한다.

6. 운영 가능성
   - 환경변수, 로깅, migration, health endpoint, 에러 처리를 갖춘다.

======================================================================
4. 저장소 구조
======================================================================

모노레포를 아래와 같이 구성하라.

/
  apps/
    desktop/                  # Tauri + React 앱
    api/                      # FastAPI 백엔드
  packages/
    types/                    # 공유 DTO / 타입 / schema
    prompts/                  # orchestration prompt templates
    config/                   # 공통 설정
    ui/                       # 필요 시 shared ui helpers
  infrastructure/
    docker/
    compose/
    env/
    scripts/
  docs/
    architecture/
    api/
    adr/
    setup/
  data/                       # 로컬 실행 시 데이터 루트(개발용 예시)
  .env.example
  README.md

만약 현재 저장소 구조가 다르다면:
- 기존 구조를 먼저 분석
- 가능한 범위에서 위 구조에 수렴시키되
- 이미 동작 중인 부분은 파괴적으로 갈아엎지 말고 점진적으로 정리한다

======================================================================
5. 먼저 해야 할 일
======================================================================

코드를 쓰기 전에 반드시 아래 순서로 수행하라.

1. 현재 저장소 상태 분석
   - 디렉터리 구조
   - 사용 중인 패키지 매니저
   - 기존 빌드 스크립트
   - 이미 구현된 기능
   - 미구현 영역
   - 중복 또는 충돌 가능성
2. 아키텍처 결정 요약(ADR 스타일, 짧고 명확하게)
3. 목표 디렉터리 트리 제안
4. DB 스키마 제안
5. 백엔드 모듈 경계 정의
6. 프론트엔드 레이아웃/컴포넌트 트리 정의
7. 오케스트레이션 그래프 설계
8. Ollama 연동 전략 확정
9. 이후 즉시 구현 시작

중요:
- 이 단계에서 멈추지 말고, 설계 후 바로 구현으로 넘어가라.
- “확인 부탁” 식으로 멈추지 마라.

======================================================================
6. 핵심 UI 요구사항
======================================================================

3패널 데스크톱 우선 UI를 구현하라.

[상단 영역]
- CPU 사용률 / 사용량
- GPU 사용률 / 사용량 (가능한 경우)
- Memory 사용률 / 사용량
- Disk 사용률 / 사용량
- GPU 사용 토글
- 작은 버튼, 작은 컨트롤, 정보 밀도 높지만 읽기 쉬운 형태
- polling 또는 streaming으로 실시간 갱신

[왼쪽 영역]
- 프로젝트 목록
- 프로젝트 생성/수정/삭제
- 프로젝트별 채팅 목록
- 채팅 생성/삭제
- 스크롤 가능
- 리사이즈 가능
- 최근 사용 기준 정렬이 유용하면 반영

[중앙 영역]
- ChatGPT 스타일 대화 타임라인
- 사용자 메시지 / AI 메시지 / 시스템 이벤트 / 오케스트레이션 이벤트 구분
- markdown 기반 AI 응답 렌더링
- 이미지/파일 업로드 및 미리보기
- drag&drop 업로드
- 스트리밍 응답 표시
- 입력창은 텍스트 + 이미지 + 일반 파일 지원
- 긴 대화에서 스크롤 성능 저하가 없도록 고려

[오른쪽 영역]
- 오케스트레이터 ON/OFF 토글
- 오케스트레이터용 모델 선택
- Ollama 모델 목록 표시
- 미다운로드 모델은 작은 Download 버튼
- 다운로드 완료 모델은 “다운됨” 상태 표시
- 모델별 사용 여부 토글
- 레이블은 왼쪽, 토글은 오른쪽
- 오케스트레이터 OFF 시 응답 순서 drag&drop 설정
- 오케스트레이터 ON 시 역할별 모델 매핑 UI
- 팝업/모달로 orchestration flow 시각화:
  - 역할
  - 선택 모델
  - 실행 순서
  - 병렬 여부
  - 중간 요약
  - 재시도
  - 리뷰/토론 관계
  - 승인 대기 상태

UI 조건:
- 반응형
- 패널 크기 조절
- 스크롤 자연스럽게
- 마지막 패널 크기/선택 상태 저장
- 버튼은 전반적으로 작게
- 데스크톱 우선이지만 너무 좁아지면 적절히 collapse/fold 고려

======================================================================
7. 기능 요구사항
======================================================================

7.1 프로젝트/채팅
- Project CRUD
- Chat thread CRUD
- 마지막으로 열었던 project/chat 복원
- soft delete 고려

7.2 대화
- 텍스트 메시지 전송
- 이미지 업로드
- 파일 업로드
- 대화 순서 보존
- 프로젝트/채팅 컨텍스트를 유지한 자연스러운 대화 흐름
- AI 응답은 JSON이 아니라 사람이 읽기 쉬운 markdown 기반 구조화 응답
- 필요 시 제목, 요약, 본문, 근거, 다음 단계 형태로 구성

7.3 파일/이미지 자산 관리
- 업로드 자료는 project/chat 기준 디렉터리에 저장
- AI 생성 산출물도 chat/message/model 기준으로 저장
- 어떤 메시지/모델/역할이 무엇을 만들었는지 추적
- 재다운로드/재열기 가능
- 썸네일/미리보기/메타데이터 관리

7.4 오케스트레이터 ON
- 사용자 요청 분석
- task decomposition
- role assignment
- model routing
- 실행 순서/병렬성 제어
- 중간 결과 병합
- critic/reviewer 또는 debate flow 가능
- retry / fallback
- 필요 시 approval gate
- step event를 UI로 스트리밍
- orchestration run history 저장

7.5 오케스트레이터 OFF
- 사용자가 선택한 모델 순서대로 응답
- independent mode / chained mode 지원
- 기본값은 independent mode
- 각 모델은 전체 대화 + 업로드 컨텍스트를 참고할 수 있어야 한다

======================================================================
8. 오케스트레이션 설계 - 필수
======================================================================

LangGraph 기반으로 설계하라.

최소 역할:
- planner
- context_resolver
- model_router
- retriever
- vision_analyst
- document_analyst
- coder
- critic
- final_responder

그래프는 최소한 아래 기능을 가져야 한다.
- intent 분석
- 대화/프로젝트/업로드 컨텍스트 수집
- 모델 capability / 하드웨어 제약 검사
- 실행 계획 수립
- 단계별 worker 실행
- 조건부 분기
- 재시도
- critic/review
- approval interrupt
- 최종 응답 조합
- step-by-step event emission
- run persistence

라우팅 정책:
1. **Rule-based routing first**
   - vision 필요한 경우 vision 가능한 모델만 후보
   - OCR/문서 처리 필요 시 해당 경로 우선
   - code task면 code-friendly 모델 우선
   - GPU 꺼짐이면 대형 GPU-heavy 모델 억제
   - 적합 모델 없으면 한계를 명확히 설명
2. **LLM-assisted routing second**
   - 규칙 필터링 이후 후보 중에서 세부 선택/역할 배치 보정

Debate / review:
- 최소 2개 모델이 상호 견제/검토 가능한 구조를 열어둔다.
- 단, 복잡도가 과도하면 first implementation은 critic/reviewer 1개 + final_responder 구조로 시작해도 된다.
- 이후 확장 가능한 interface를 유지한다.

======================================================================
9. Ollama 연동 - 필수
======================================================================

Ollama 연동을 별도 service/client abstraction으로 구현하라.

반드시 제공할 인터페이스:
- health_check()
- list_models()
- sync_registry()
- pull_model(model_name)
- delete_model(model_name)
- chat(model_name, messages, images=None, options=None)
- embeddings(model_name, input)
- unload_model(model_name)   # 가능하면
- prewarm_model(model_name)  # 가능하면

요구사항:
- Ollama host endpoint는 환경변수 기반
- 기본값은 localhost:11434
- 모델 하드코딩 금지
- registry에 capability metadata 관리
- vision / embeddings / reasoning / tools 지원 여부 관리
- 다운로드 진행률을 UI에 전달할 수 있게 event 또는 polling 설계
- Ollama 미기동 상태에서 graceful handling

======================================================================
10. 멀티모달 / 업로드 / RAG
======================================================================

단순 파일 첨부가 아니라, 검색 가능한 프로젝트 자료 체계로 구현하라.

인제스트 파이프라인:
- MIME 판별
- 원본 저장
- 메타 생성
- 텍스트 추출
- 필요 시 OCR
- 청크 분리
- 임베딩 생성
- Qdrant 인덱싱
- asset/message/chat/project 연계 저장

대화 시:
- 현재 chat 우선
- 필요 시 project 범위까지 확장
- 관련 chunk retrieval
- 필요한 범위만 모델 입력에 포함
- 너무 큰 원문 전체를 무작정 프롬프트에 넣지 말 것

이미지 처리:
- vision-capable 모델 사용
- 필요 시 이미지 설명/분석 결과를 중간 컨텍스트로 저장 가능

출처 표현:
- 답변에 활용한 업로드 자료는 사람이 읽기 쉬운 방식으로 참조할 수 있게 설계
- 예: 파일명, 페이지 범위, 자산명, 첨부 미리보기 연결

======================================================================
11. 하드웨어 모니터링
======================================================================

실시간 시스템 상태를 제공하라.

최소 수집 항목:
- CPU %
- Memory 사용량/사용률
- Disk 사용량/사용률
- GPU 사용량/사용률 (가능한 경우)
- GPU 존재 여부
- GPU 사용 가능 토글 상태

구현 원칙:
- OS 차이에 대한 abstraction 제공
- Python backend에서 psutil 활용 가능
- GPU는 vendor/OS 상황에 따라 graceful fallback
- 수집 불가 시 UI를 조용히 degrade
- metric fetch 실패가 앱 전체 오류로 번지면 안 됨

======================================================================
12. 데이터 모델
======================================================================

아래 테이블/엔티티를 포함하라.

Project
- id
- name
- description
- created_at
- updated_at
- deleted_at nullable

ChatThread
- id
- project_id
- title
- created_at
- updated_at
- deleted_at nullable

Message
- id
- project_id
- chat_thread_id
- role (user / assistant / system / orchestrator)
- content_markdown
- plain_text_cache
- model_name nullable
- model_role nullable
- sequence_no
- created_at

Asset
- id
- project_id
- chat_thread_id
- message_id nullable
- source_type (user_upload / ai_generated / system_derived)
- asset_type (image / file / text / other)
- mime_type
- original_filename
- stored_path
- derived_metadata_json
- producing_model nullable
- producing_role nullable
- created_at

ModelRegistry
- id
- model_name
- provider
- downloaded
- enabled
- supports_vision
- supports_tools
- supports_embeddings
- supports_reasoning
- preferred_roles json
- sort_order nullable
- last_seen_at

OrchestrationRun
- id
- project_id
- chat_thread_id
- user_message_id
- status
- graph_name
- started_at
- ended_at
- final_message_id nullable

OrchestrationStep
- id
- orchestration_run_id
- step_name
- assigned_role
- model_name
- input_summary
- output_summary
- status
- retry_count
- started_at
- ended_at

추가로 필요한 보조 엔티티가 있으면 합리적으로 추가하라.
반드시 migration을 작성하고, 인덱스와 FK를 신경 써라.

======================================================================
13. 파일 저장 구조
======================================================================

로컬 파일 저장 구조를 일관되게 유지하라.

예시:
data/projects/{project_id}/
  chats/{chat_id}/
    uploads/
    derived/
    ai_outputs/{message_id}/{model_name}/

규칙:
- 파일명 sanitize
- path traversal 방지
- collision-safe naming
- DB와 filesystem metadata 동기화
- 파일만 믿지 말고 DB를 source of truth로 관리

======================================================================
14. 백엔드 API 요구사항
======================================================================

FastAPI로 다음 계열 endpoint를 구현하라.

Projects
- create
- list
- get
- update
- delete

Chats
- create
- list by project
- get
- delete

Messages
- list by chat
- create user message
- stream assistant response
- stream orchestration events

Assets
- upload
- list by chat
- get metadata
- download/open reference

Models
- list
- sync with Ollama
- pull/download
- delete
- enable/disable
- update role preferences
- update sort order

Orchestration
- run
- stream events
- get run details
- list runs
- approve pending step
- reject pending step

System
- health
- hardware metrics
- config snapshot (safe subset only)

원칙:
- DTO 명확화
- 에러 응답 일관성
- streaming은 SSE 우선
- OpenAPI 자동 노출
- frontend에서 쓰기 쉬운 response shape 유지

======================================================================
15. 프론트엔드 구현 원칙
======================================================================

필수 구성:
- App shell
- top metrics bar
- left project/chat sidebar
- center conversation panel
- right model/orchestrator panel
- orchestration modal
- upload preview components
- markdown message renderer
- streaming message UI
- error/empty/loading states
- toast notifications
- persisted panel sizes and last selections

상태 관리:
- 서버 상태는 TanStack Query
- UI 상태는 Zustand
- 타입은 backend DTO와 강하게 맞춘다

컴포넌트 원칙:
- presentational / container 성격 분리
- 너무 큰 god component 금지
- hooks를 재사용 가능하게 분리
- 컴포넌트명, props, 폴더 구조 일관성 유지

======================================================================
16. UX 원칙
======================================================================

- 버튼은 작고 촘촘하게
- 전체적으로 modern clean desktop UI
- 정보 밀도는 높지만 읽기 쉬워야 함
- 키보드 친화성 고려
- 긴 응답도 보기 편해야 함
- 모델 capability badge 제공:
  - vision
  - reasoning
  - embeddings
  - tools
  - downloaded
  - enabled
- AI 답변은 polished assistant 형태로 보여야 함
- raw JSON을 메인 표시 형식으로 쓰지 말 것

======================================================================
17. 보안 / 안정성 / 견고성
======================================================================

반드시 신경 쓸 것:
- 파일명 sanitization
- path traversal 방지
- 업로드 MIME / size validation
- Ollama 다운/타임아웃 graceful handling
- 다운로드 실패 graceful handling
- orchestration step failure logging
- 환경변수 기반 설정
- 프론트엔드에 secret 노출 금지
- 예외가 발생해도 앱 전체가 망가지지 않게 boundary 처리

======================================================================
18. 로깅 / 추적 / 관측성
======================================================================

구현하라:
- 구조화 로그
- request correlation id
- orchestration run id
- orchestration step 로그
- dev 모드에서 읽기 쉬운 로그
- UI debug trace panel(가능하면)
- 주요 오류에 대한 사용자 친화적 메시지

======================================================================
19. 테스트 전략
======================================================================

반드시 기본 테스트 뼈대를 포함하라.

Backend:
- pytest
- service 단위 테스트
- routing policy 테스트
- API smoke test

Frontend:
- vitest
- react testing library
- 주요 UI 상태/컴포넌트 렌더링 테스트

E2E:
- Playwright 가능하면 포함
- 최소한 프로젝트 생성 → 채팅 생성 → 메시지 전송 → 모델 응답 스트림 기본 경로 검증

======================================================================
20. 개발 단계(마일스톤)
======================================================================

아래 순서로 진행하라. 각 단계 종료 시 빌드 가능한 상태를 유지한다.

[Milestone 1]
- 모노레포 스캐폴딩
- desktop shell 기본 구성
- api 기본 구성
- Docker Compose(postgres, qdrant)
- .env.example
- base DB schema + migration
- 기본 3패널 레이아웃
- project/chat CRUD
- README 실행 방법

수용 기준:
- 앱 실행 가능
- 프로젝트/채팅 생성 및 목록 표시 가능
- 기본 레이아웃 동작
- migration 정상 수행

[Milestone 2]
- Ollama client/service
- model registry 동기화
- 모델 목록 UI
- 다운로드 버튼/상태 표시
- 단일 모델 chat streaming

수용 기준:
- Ollama 연결 상태 확인 가능
- 모델 목록 확인 가능
- 다운로드 요청 가능
- 단일 모델 응답 스트리밍 가능

[Milestone 3]
- 파일/이미지 업로드
- asset storage
- preview UI
- ingestion pipeline
- retrieval support

수용 기준:
- 업로드 가능
- chat/project별 파일 정리 가능
- retrieval 기반 context 주입 시작

[Milestone 4]
- LangGraph orchestration
- role routing
- step persistence
- event streaming
- orchestration modal visualization

수용 기준:
- 오케스트레이터 ON 시 역할 분해 및 단계 이벤트 확인 가능
- step 기록 조회 가능

[Milestone 5]
- multi-model ordered response mode
- independent / chained mode
- critic/reviewer loop
- AI generated artifacts tracking

수용 기준:
- 여러 모델 순차 응답
- critic/review 동작
- 생성 산출물 저장/조회 가능

[Milestone 6]
- 테스트 보강
- packaging
- 문서화
- polish
- 성능/UX 개선

======================================================================
21. 출력 방식 규칙
======================================================================

매 응답에서 다음 규칙을 지켜라.

1. 먼저 현재 작업 목표를 1~3문장으로 요약
2. 그 다음 실제 변경 사항을 파일 단위로 제시
3. 필요한 경우 핵심 코드 조각을 포함
4. 실행/검증 방법을 명확히 제시
5. 불필요한 장문 이론 설명은 줄이고 실제 구현을 우선
6. 핵심 의사결정은 짧게 이유를 남긴다
7. 작업이 길어지면 중간 진행상황을 간결히 공유하되, 멈추지 말고 계속 구현한다

======================================================================
22. 금지 사항
======================================================================

- 핵심 경로에서 TODO만 남기고 끝내기
- “예시입니다” 수준의 껍데기 코드만 대량 생성
- 빌드 불가능한 상태로 방치
- 기존 코드 무시 후 전면 재작성
- 모델명 하나에 과도하게 결합된 설계
- raw JSON을 사용자 메인 응답 UI로 그대로 출력
- 검증 없이 무작정 대규모 리팩터링

======================================================================
23. 추가 권장 기능
======================================================================

구조를 망치지 않는 범위에서 다음을 추가해도 좋다.
- project memory summary
- conversation search
- pinned messages
- orchestration templates
- performance mode selector (Fast / Balanced / Quality / Debate / Review-heavy)
- import/export project package
- local backup/restore
- generated artifact provenance viewer

======================================================================
24. 지금 바로 시작할 작업
======================================================================

지금 즉시 아래 순서로 시작하라.

1. 현재 저장소 스캔
2. 구조/기술 스택/구현 상태 파악
3. 목표 구조와 차이 분석
4. Milestone 1 구현 시작
5. 필요한 파일 생성/수정
6. 실행 방법 문서화
7. 이후 순차적으로 다음 milestone 진행

중요:
- broad clarification 없이 진행
- 코드 우선
- 각 단계마다 runnable state 유지
- repository의 현재 상태를 존중하면서 점진적으로 완성도를 끌어올릴 것

이제 구현을 시작하라.
```

---

## 후속 제어 프롬프트 1 — 이어서 구현

```text
현재 저장소 상태를 먼저 분석하고, 이미 구현된 내용을 보존하면서 `multi-orche-ai-chat` 개발을 계속 진행하라.

규칙:
- 기존 동작 코드를 불필요하게 뒤엎지 말 것
- build/run 가능 상태를 유지할 것
- 새 기능을 넣을 때는 frontend + backend + persistence를 함께 연결할 것
- 설정 변경 시 README와 .env.example도 함께 갱신할 것
- 핵심 로직에는 테스트를 추가할 것

현재 우선순위:
[여기에 현재 우선순위를 넣어라]
예시:
- Ollama 모델 패널 완성
- asset upload pipeline 구현
- orchestration graph 및 step event stream 구현
- drag and drop 모델 순서 기능 구현
```

---

## 후속 제어 프롬프트 2 — 오케스트레이션 집중

```text
`multi-orche-ai-chat`의 오케스트레이션 서브시스템만 집중적으로 구현하라.

필수 구현:
- LangGraph 기반 상태 모델
- planner node
- context_resolver node
- model_router node
- worker execution nodes
- critic / reviewer node
- final_responder node
- retry / fallback policy
- approval interrupt flow
- orchestration run persistence
- UI에 전달 가능한 step event DTO
- popup/modal 친화적 trace data 구조

규칙:
- rule-based routing을 먼저 적용하고, 그 다음 LLM-assisted routing을 적용할 것
- vision / document / code / reasoning 역할 분배를 지원할 것
- provider-agnostic interface를 유지하되 첫 provider는 Ollama로 구현할 것
- 각 orchestration step은 audit 가능해야 하며, 가능한 범위에서 resumable 구조를 고려할 것
```

---

## 후속 제어 프롬프트 3 — UI/UX 집중

```text
`multi-orche-ai-chat`의 데스크톱 UI/UX만 집중적으로 고도화하라.

필수 구현:
- 반응형 3패널 레이아웃
- 상단 hardware metrics bar
- 작은 버튼 스타일 시스템
- resizable panels
- scrollable side panels
- ChatGPT 스타일 message timeline
- markdown assistant renderer
- file/image upload + preview UX
- model download/toggle/status UX
- orchestrator modal with execution flow visualization
- manual multi-model mode drag-and-drop ordering

디자인 원칙:
- desktop-first
- dense but readable
- modern clean spacing
- strong empty/loading/error states
- keyboard-friendly
- last active selections and panel sizes persisted
```

---

## 권장 사용 팁
1. 첫 실행은 반드시 **메인 프롬프트 전체**를 넣습니다.
2. 저장소가 어느 정도 만들어진 뒤에는 후속 프롬프트를 조합합니다.
3. 모델이 장황하게 설명만 하려 하면, 다음 문장을 추가합니다.  
   **“설명보다 코드와 파일 변경을 우선하라. 핵심 경로에서 의사코드로 멈추지 마라.”**
4. 큰 단위 구현이 끝날 때마다 빌드/실행/테스트 결과를 요구합니다.
5. 오케스트레이션이 약하면 “오케스트레이션 집중” 프롬프트를 따로 넣어 강화합니다.

---

## 빠른 복사용 한 줄 보강 문구
```text
당신은 조언자가 아니라 주 구현자다. 추상적 설명보다 동작하는 코드, 실제 파일 변경, 실행 가능한 구조를 우선하라. 핵심 경로에서 TODO나 의사코드로 멈추지 말고, 저장소를 읽은 뒤 바로 구현을 진행하라.
```
