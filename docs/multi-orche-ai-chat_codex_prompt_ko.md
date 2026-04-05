# multi-orche-ai-chat Codex 전용 초정밀 통합 프롬프트

이 문서는 **Codex가 `multi-orche-ai-chat`를 처음부터 실제 구현할 수 있도록 설계한 한글 실행 지시서**입니다.  
목표는 “좋은 제안”이 아니라 **실제 파일 생성·수정·실행·테스트까지 이어지는 구현 지시**입니다.

## 사용 방법

1. 아래 **메인 통합 프롬프트**를 Codex에 첫 입력으로 넣습니다.
2. 한 번에 너무 많은 작업이 진행되면, 아래 **후속 작업 프롬프트**를 사용해 한 기능씩 이어갑니다.
3. 이미 생성된 저장소를 다시 정렬하거나 부족한 구현을 바로잡고 싶다면 **보정/재정렬 프롬프트**를 사용합니다.
4. Codex가 설명만 길게 하고 실제 코드를 덜 만들면, 문서 맨 아래의 **강화 문구**를 프롬프트 맨 앞에 추가합니다.

## 메인 통합 프롬프트

```text
너는 조언자가 아니라 이 프로젝트의 주 구현자다.
설명 위주로 답하지 말고, 현재 저장소 상태를 먼저 분석한 뒤 필요한 파일을 직접 생성·수정해서 기능을 구현하라.
핵심 경로에서는 의사코드로 멈추지 말고, 실행 가능한 코드로 완성하라.
작업 중에는 기존 코드를 불필요하게 갈아엎지 말고, 구조를 유지하면서 점진적으로 확장하라.
각 단계가 끝날 때마다 빌드 가능 상태와 실행 가능 상태를 유지하라.
애매한 사소한 확인 질문은 하지 말고, 시니어 엔지니어 수준의 합리적 판단으로 진행하라.
문제가 있으면 우회 가능한 최소 동작 버전을 먼저 만들고, 이후 고도화하라.

프로젝트명:
multi-orche-ai-chat

제품 정의:
이 프로젝트는 Ollama 기반 로컬 멀티모델 AI 채팅 및 오케스트레이션 데스크톱 워크벤치다.
단순 웹 채팅 앱이 아니라, 프로젝트 단위 멀티모달 대화와 다중 AI 모델 제어를 중심으로 하는 로컬 퍼스트 생산성 도구를 구현한다.

핵심 목표:
1. 로컬 PC에서 Ollama 모델을 검색, 다운로드, 선택, 실행할 수 있어야 한다.
2. 프로젝트별로 대화와 첨부 파일, 생성 결과물을 분리 관리해야 한다.
3. 텍스트, 이미지, 파일을 함께 다루는 멀티모달 대화를 지원해야 한다.
4. 오케스트레이터 사용 시 요청을 자동으로 분해하고 역할별 모델을 선택하여 단계적으로 실행해야 한다.
5. 오케스트레이터 미사용 시 사용자가 선택한 복수 모델이 정해진 순서 또는 체인 규칙에 따라 응답해야 한다.
6. UI는 데스크톱 퍼스트이며, 작은 버튼, 3패널 레이아웃, 실시간 하드웨어 정보 표시를 갖춰야 한다.
7. 결과물은 실제로 실행 가능하고 테스트 가능한 수준으로 구현되어야 한다.

절대 지켜야 할 기술 방향:
- Desktop shell: Tauri v2
- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand, TanStack Query, react-resizable-panels, react-router
- Backend: Python 3.12+, FastAPI, LangGraph, Pydantic v2, SQLAlchemy 2.x, Alembic
- Storage: PostgreSQL, Qdrant, local filesystem
- Model runtime: host OS에 설치된 Ollama를 기본값으로 사용
- Dev infra: Docker Compose
- Tests: pytest, vitest, React Testing Library, Playwright
- Packaging: Tauri build 기반 로컬 데스크톱 배포

기본 런타임 전략:
- Ollama는 기본적으로 호스트 OS에 네이티브 설치된 인스턴스를 사용한다.
- 앱 계층과 백엔드는 컨테이너화 가능해야 하지만, Ollama까지 기본적으로 컨테이너에 넣지 않는다.
- 로컬 파일 접근, 하드웨어 모니터링, GPU 사용 토글, 경로 관리가 중요하므로 데스크톱 앱 중심으로 설계한다.
- 단, 추후 선택적으로 Ollama 컨테이너 모드도 확장 가능하도록 provider abstraction을 설계한다.

모노레포 구조:
/
  apps/
    desktop/              # Tauri + React
    api/                  # FastAPI + LangGraph + SQLAlchemy
  packages/
    types/                # 프론트/백엔드 공유 타입
    config/               # 공통 설정
    prompts/              # 오케스트레이션 프롬프트 템플릿
    ui/                   # 공통 UI 유틸 또는 공유 컴포넌트
  infrastructure/
    compose/
    scripts/
    env/
  docs/
    architecture/
    api/
    adr/
    runbooks/

필수 산출물:
- 모노레포 디렉토리 구조
- 실제 소스 코드 파일
- 환경변수 예시(.env.example)
- Docker Compose
- Alembic 마이그레이션
- DB 모델 및 스키마
- FastAPI 라우터/서비스
- React/Tauri 화면 및 상태관리
- Ollama 클라이언트
- LangGraph 오케스트레이터
- 업로드/저장/인덱싱 파이프라인
- 테스트 코드
- README 및 실행 가이드
- 아키텍처 문서 및 핵심 ADR

기능 요구사항 - UI:
1. 상단 영역
- CPU, GPU, Memory, Disk 실시간 사용률/사용량 표시
- GPU 사용 가능 장비 존재 시 GPU 사용 여부 토글 표시
- 작고 조밀한 컨트롤 사용
- 상태 polling 또는 SSE/WebSocket 방식으로 갱신

2. 왼쪽 영역
- 프로젝트 목록
- 프로젝트 생성/수정/삭제
- 프로젝트별 채팅 목록
- 채팅 생성/삭제
- 최근 접근 항목 유지
- 스크롤 및 리사이즈 지원

3. 중앙 영역
- ChatGPT 스타일의 타임라인형 대화 UI
- user / assistant / system / orchestrator 이벤트 구분 표시
- 텍스트 입력
- 이미지 업로드
- 일반 파일 업로드
- 업로드 파일 미리보기
- AI 응답의 markdown 렌더링
- 스트리밍 응답 표시
- 대화 흐름이 자연스럽게 이어져야 함
- raw JSON을 메인 응답 포맷으로 노출하지 말 것

4. 오른쪽 영역
- 오케스트레이터 ON/OFF 토글
- 오케스트레이터용 모델 선택
- Ollama 모델 목록
- 미다운로드 모델은 Download 버튼
- 다운로드 완료 모델은 설치 상태 표시
- 모델 사용 토글
- 오케스트레이터 OFF일 때 모델 응답 순서 변경 drag-and-drop
- 오케스트레이터 ON일 때 역할-모델 매핑 UI
- 시각적 팝업/모달에서 역할, 모델, 실행 순서, 중간 결과, 재시도, 승인 대기, debate/review 관계 표시

반응형/레이아웃 요구사항:
- 데스크톱 우선
- 각 영역 크기 조절 가능
- 각 영역 스크롤 지원
- 창 크기에 따라 레이아웃이 무너지지 않아야 함
- 버튼은 작지만 충분히 클릭 가능해야 함
- 마지막 패널 크기와 선택 상태를 저장해야 함

기능 요구사항 - 대화:
- 텍스트 입력 가능
- 이미지 업로드 가능
- 일반 파일 업로드 가능
- 첨부 자료는 프로젝트/채팅 단위 디렉토리에 저장
- 메시지는 입력 순서대로 유지
- 전체 대화 문맥을 바탕으로 응답 생성
- 첨부 이미지/파일과 과거 대화 내용을 함께 참고해야 함
- AI가 생성한 파일/이미지/문서/코드도 저장하고 메타데이터 추적
- 어떤 대화에서 어떤 모델이 언제 생성했는지 조회 가능해야 함

파일/산출물 저장 구조:
data/
  projects/{project_id}/
    chats/{chat_id}/
      uploads/
      derived/
      ai_outputs/{message_id}/{model_name}/

DB에는 최소한 다음 정보를 저장:
- project_id
- chat_id
- message_id
- asset_id
- source_type(user_upload / ai_generated / system_derived)
- asset_type(image / file / text / other)
- original_filename
- mime_type
- stored_path
- derived_metadata
- producing_model
- producing_role
- created_at

오케스트레이터 ON 동작 요구사항:
- 사용자 입력 분석
- intent 분류
- 대화 맥락 수집
- 첨부 파일/이미지/검색 결과 수집
- 역할 정의
- 각 역할에 적합한 모델 선택
- 순차 또는 병렬 실행
- 중간 결과 요약/병합
- critic/reviewer를 통한 검수
- 필요 시 재시도 또는 fallback
- 고위험 작업이나 파일 생성, 외부 액션 전 사용자 승인 요청 가능
- 실행 흐름을 UI에 시각적으로 제공

오케스트레이터 OFF 동작 요구사항:
- 사용자가 오른쪽 패널에서 모델 선택
- 선택 모델의 응답 순서 지정 가능
- 각 모델은 전체 대화와 첨부 문맥을 참고해 답변
- 독립 응답 모드와 체인 응답 모드를 지원
- 기본값은 독립 응답 모드
- 필요 시 마지막에 비교 또는 요약 뷰 제공

오케스트레이션 구현 원칙:
- LangGraph 사용
- rule-based routing을 먼저 적용
- 이후 LLM-assisted routing으로 세부 보정
- 모든 step은 추적 가능해야 함
- 모든 run은 재현 가능한 로그를 남겨야 함
- 중간 결과는 사람이 읽을 수 있는 summary 형태로 저장
- run, step, retry, approval 상태를 DB에 남길 것

최소 역할 집합:
- planner
- context_resolver
- model_router
- retriever
- vision_analyst
- document_analyst
- coder
- critic
- final_responder

모델 라우팅 규칙 예시:
- 이미지가 있으면 vision 지원 모델만 후보
- OCR 또는 문서 분석 필요 시 document path 선행
- 코드 생성 요청은 coding-capable 모델 우선
- 긴 추론은 reasoning-capable 모델 우선
- GPU OFF면 대형 모델 또는 GPU 의존 모델 제외
- 로컬 모델로 불가능한 기능이면 한계를 명확히 설명
- 사용자가 특정 모델을 고정한 경우 우선 존중하되, capability mismatch면 경고

Ollama 통합 요구사항:
백엔드에 명확한 Ollama client abstraction을 구현하라.
필수 메서드:
- health_check()
- list_models()
- sync_model_registry()
- pull_model(model_name)
- delete_model(model_name)
- chat(model_name, messages, images=None, options=None)
- embeddings(model_name, input)
- warm_model(model_name)
- unload_model(model_name)

필수 동작:
- Ollama 서버 연결 확인
- 설치 모델 목록 조회
- 모델 다운로드 진행 상태 반영
- 모델 capability 메타 관리
- 멀티모달 모델과 텍스트 모델 구분
- 추후 provider 확장 가능하도록 인터페이스 분리

모델 레지스트리 요구사항:
ModelRegistry 테이블에 최소 저장:
- id
- model_name
- provider
- downloaded
- enabled
- supports_vision
- supports_tools
- supports_embeddings
- supports_reasoning
- preferred_roles
- last_seen_at
- sort_order
- metadata_json

멀티모달/RAG 요구사항:
- 파일 업로드 시 MIME type 판별
- 원본 저장
- 텍스트 추출
- 필요 시 OCR
- chunking
- embedding 생성
- Qdrant 인덱싱
- project/chat/message/asset 기준으로 source tracing 가능해야 함
- 추론 시 관련 청크를 retrieve해서 모델 컨텍스트로 제공
- 대형 문서를 raw로 모델에 그대로 넣지 말고 retrieval + 요약 방식을 사용

지원 우선 파일 타입:
- txt
- md
- pdf
- docx
- xlsx
- csv
- png
- jpg
- jpeg
- webp

하드웨어 모니터링 요구사항:
- CPU usage
- memory usage
- disk usage
- GPU usage
- GPU memory
- GPU availability
- graceful fallback
- 지원되지 않는 환경에서 앱이 죽으면 안 됨
- psutil 기반 기본 구현
- GPU는 가능한 범위에서 vendor-aware 구현, 없으면 unsupported 처리

필수 DB 스키마:
Project
- id
- name
- description
- created_at
- updated_at
- deleted_at

ChatThread
- id
- project_id
- title
- created_at
- updated_at
- deleted_at

Message
- id
- project_id
- chat_thread_id
- role
- content_markdown
- plain_text_cache
- model_name
- model_role
- sequence_no
- created_at

Asset
- id
- project_id
- chat_thread_id
- message_id
- source_type
- asset_type
- mime_type
- original_filename
- stored_path
- derived_metadata_json
- producing_model
- producing_role
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
- preferred_roles_json
- sort_order
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
- final_message_id

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

설계 원칙:
- SQLAlchemy 2.x typed mapping 사용
- Alembic migration 포함
- soft delete가 필요한 엔티티는 deleted_at 사용
- 주요 조회 컬럼에 인덱스 추가
- sequence_no로 메시지 순서 보장

API 설계 요구사항:
Projects
- create/list/get/update/delete

Chats
- create/list/get/delete

Messages
- list
- create user message
- stream assistant responses
- list message assets

Assets
- upload
- list by chat
- fetch metadata
- download/open
- list generated outputs

Models
- list registry
- sync with Ollama
- pull/download
- delete
- toggle enabled
- update sort order
- update role preferences

Orchestration
- run
- stream execution events
- get run detail
- get run history
- approve step
- reject step

System
- health
- hardware metrics
- app config
- ollama connectivity

프론트엔드 구현 요구사항:
- 타입 안정성 유지
- API contract를 types package 또는 공용 DTO로 정리
- 페이지/상태/컴포넌트 분리
- 메시지 타임라인
- markdown renderer
- 첨부 preview
- 드래그 앤 드롭 업로드
- 모델 패널
- orchestration modal
- 토스트 알림
- empty/loading/error state
- optimistic update를 신중하게 사용
- panel size, selected project/chat, mode 상태를 로컬 저장

보안/안정성 요구사항:
- 파일명 sanitize
- path traversal 방지
- 업로드 크기 제한
- 허용 MIME 정책
- Ollama 미실행 상태 graceful handling
- 모델 다운로드 실패 graceful handling
- 타임아웃과 재시도 정책
- 에러 로깅
- 프론트에 secret 노출 금지
- 설정은 환경변수 기반으로 분리

관측성 요구사항:
- structured logging
- request ID
- orchestration run ID
- step 단위 로그
- frontend error boundary
- dev mode에서 디버그 로그 강화
- 선택적으로 trace panel 제공

UX 세부 요구사항:
- small buttons
- dense but readable layout
- modern desktop-first UI
- clear badges: downloaded, active, vision, reasoning, embeddings, orchestrator role
- AI 응답은 요약 + 구조화된 설명 + 다음 행동 또는 참고 정보 형태로 표시
- 사람이 읽기 좋은 markdown을 사용하되 과도한 장식은 피할 것

테스트 요구사항:
- backend unit test
- service test
- API integration test
- frontend component test
- basic e2e smoke test
- 최소한 health, project/chat CRUD, model registry sync, message flow, upload flow, orchestration run 기본 경로 테스트 포함

문서화 요구사항:
- README
- run instructions
- architecture overview
- ADR: 왜 Tauri인지, 왜 host Ollama인지, 왜 LangGraph인지
- API summary
- env example
- troubleshooting

작업 순서:
Milestone 1
- 모노레포 스캐폴딩
- Tauri + React + FastAPI 기본 구조
- Docker Compose(Postgres, Qdrant)
- DB 초기 스키마
- 3패널 UI + 상단 바
- 프로젝트/채팅 CRUD
- 기본 README

Milestone 2
- Ollama client
- model registry
- 우측 패널 모델 목록/동기화/다운로드/토글
- 단일 모델 대화
- assistant message 저장
- 스트리밍 응답

Milestone 3
- 파일/이미지 업로드
- asset 저장 구조
- preview
- ingestion pipeline
- retrieval 연동

Milestone 4
- LangGraph orchestrator
- run/step persistence
- orchestration event stream
- 역할-모델 매핑
- orchestration modal

Milestone 5
- 수동 멀티모델 순차 응답
- 독립/체인 모드
- critic/reviewer 흐름
- generated artifact tracking

Milestone 6
- 하드웨어 메트릭 실제 연결
- UX polish
- 테스트 강화
- packaging
- 문서 보강

매 턴 출력 형식:
1. 이번 턴 목표
2. 현재 저장소 분석 결과
3. 변경할 파일 목록
4. 실제 코드 생성/수정
5. 실행 방법
6. 테스트 방법
7. 남은 리스크와 다음 우선순위

금지사항:
- 핵심 기능을 TODO만 남기고 끝내지 말 것
- 실행 불가능한 의사코드만 제시하지 말 것
- 이미 있는 파일을 이유 없이 전부 재작성하지 말 것
- 사용자가 묻지 않은 사소한 확인 질문 남발 금지
- raw JSON을 최종 UI 답변 포맷으로 삼지 말 것
- 업로드 경로를 사용자 입력 문자열에 직접 의존하지 말 것
- 하드웨어/GPU 미지원 환경에서 앱이 죽게 만들지 말 것

완료 기준:
- 로컬에서 실행 가능
- DB migration 가능
- API 서버 기동 가능
- 프론트 앱 기동 가능
- Tauri dev 실행 가능
- 프로젝트/채팅/메시지 흐름 동작
- 모델 목록 및 다운로드 UI 동작
- 최소 1개 모델로 assistant 응답 생성 가능
- 파일 업로드 및 저장 추적 가능
- 오케스트레이터 기본 경로 동작
- 테스트 스위트 기본 경로 통과
- README 기준 설치/실행이 재현 가능

지금 당장 시작할 작업:
1. 현재 저장소를 분석하라.
2. 목표 구조와 실제 구조의 차이를 식별하라.
3. 필요한 폴더와 파일을 생성하라.
4. Tauri + React + FastAPI + Compose 기본 실행 경로를 만들라.
5. DB 모델과 Alembic을 구성하라.
6. 프로젝트/채팅 CRUD와 3패널 UI를 실제로 연결하라.
7. 이후 Milestone 순서대로 끊김 없이 구현을 이어가라.

이제 바로 구현을 시작하라.
```

## 후속 작업 프롬프트

```text
현재 저장소 상태를 기준으로 이어서 작업하라.
먼저 기존 파일을 모두 읽고, 이미 구현된 부분은 유지하되 구조적으로 부족한 부분만 정확히 보강하라.

이번 턴의 단일 목표:
[여기에 한 가지 목표를 입력]

예시:
- Ollama 모델 목록/다운로드/토글 UI 및 API 구현
- assistant 응답 스트리밍 구현
- Asset 업로드 및 프로젝트/채팅별 저장 구조 구현
- LangGraph 오케스트레이터와 step persistence 구현
- 하드웨어 메트릭 API 및 상단 바 연결

작업 규칙:
- 목표 하나에 집중할 것
- 관련 없는 리팩터링 금지
- 백엔드/프론트엔드/DB가 실제로 연결되도록 구현할 것
- 변경 파일 목록을 먼저 제시하고 실제 코드 수정으로 이어갈 것
- 작업 후 실행 방법과 테스트 방법을 반드시 제시할 것
- build/run이 깨지지 않게 유지할 것
```

## 보정/재정렬 프롬프트

```text
현재 저장소를 점검하고, multi-orche-ai-chat의 목표 아키텍처와 비교하여 부족하거나 잘못 구현된 부분을 수정하라.

점검 기준:
- Tauri 데스크톱 구조 존재 여부
- FastAPI + LangGraph + Alembic + SQLAlchemy 구조 완성도
- Ollama 클라이언트 및 모델 레지스트리 존재 여부
- 파일 업로드 및 Asset 추적 구조 존재 여부
- Qdrant retrieval pipeline 존재 여부
- 오케스트레이터 run/step persistence 존재 여부
- 상단 하드웨어 모니터링 실데이터 존재 여부
- 우측 패널 모델 제어 UI 존재 여부
- assistant 응답 스트리밍 존재 여부
- 테스트 및 문서화 수준

수정 원칙:
- 구조는 살리고, 제품 비전에 맞지 않는 부분을 보강할 것
- placeholder를 실제 기능으로 바꿀 것
- 핵심 기능은 의사코드가 아니라 동작 코드로 만들 것
- 필요한 경우 migration, schema, API, UI를 모두 연쇄 수정할 것
```

## Codex 제어를 더 강하게 하고 싶을 때 맨 앞에 붙일 문구

```text
너는 조언자가 아니라 주 구현자다.
현재 저장소를 먼저 분석하고, 실제 파일을 생성/수정해서 기능을 완성하라.
핵심 경로에서는 의사코드로 멈추지 말고 실행 가능한 코드로 구현하라.
말보다 코드와 실행 결과를 우선하라.
```

## 권장 운용 방식

### 처음 시작할 때
- 메인 통합 프롬프트 전체를 사용
- 저장소가 비어 있거나 크게 잘못된 경우 적합

### 이미 일부 코드가 있을 때
- 메인 통합 프롬프트 대신 보정/재정렬 프롬프트 사용
- 그 다음 후속 작업 프롬프트로 기능별 확장

### 가장 추천하는 진행 순서
1. 메인 통합 프롬프트
2. `이번 턴의 단일 목표`에 `Tauri + FastAPI + Compose + CRUD` 지정
3. 다음 턴에 `Ollama 모델 목록/다운로드/토글`
4. 다음 턴에 `assistant 응답 스트리밍`
5. 다음 턴에 `Asset 업로드 + 저장 구조 + Qdrant`
6. 다음 턴에 `LangGraph 오케스트레이터`
7. 다음 턴에 `수동 멀티모델 모드`
8. 마지막에 `테스트/문서/패키징`

## Codex가 자주 놓치는 항목 체크리스트

- Tauri를 빼고 일반 웹앱으로만 만들지 않았는가
- Ollama 연동을 placeholder가 아니라 실제 API 호출로 구현했는가
- 모델 다운로드 진행 상태를 UI에 반영했는가
- assistant 응답을 실제로 생성하고 저장하는가
- 스트리밍 응답이 동작하는가
- 파일 업로드가 project/chat별 디렉토리에 저장되는가
- Asset 메타데이터를 DB에 남기는가
- Qdrant retrieval이 실제로 연결되는가
- 오케스트레이터 run/step이 DB에 저장되는가
- 우측 패널이 단순 설명이 아니라 실제 제어 UI인가
- 상단 하드웨어 바가 `--%` placeholder가 아니라 실데이터인가
- 테스트와 README가 실행 기준으로 정리되어 있는가

## 마지막 팁

Codex에 너무 긴 맥락을 매번 다시 넣기보다,  
**첫 턴은 메인 프롬프트 전체**,  
그 다음부터는 **후속 작업 프롬프트 + 이번 턴 목표 한 줄** 방식이 가장 안정적입니다.
