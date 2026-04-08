# Post-Merge Branch Plan (Execution Roadmap)

## 1) Current release candidate scope

- Core backend/API + orchestration + retrieval + approval flow + role mapping.
- Desktop UI + doctor preflight + runbook + smoke tests.
- RC 수준의 문서화 및 known limitations 명시.

> 즉, 현재 브랜치는 **기능 부재가 아니라 운영/확장 관점의 후속 정리** 단계입니다.

## 2) Accepted limitations

- Backend 별도 프로세스 전제(번들 단독 완결 불가).
- Ollama/Qdrant/DB availability에 강결합.
- CI/운영 자동화 미완료(수동 절차 의존 구간 존재).
- 긴 타임라인/대용량 자산에서 UX/perf 최적화 여지.

## 3) Branch plan (3~6개)

## A. `postmerge/production-hardening-gates`
- 목적: 운영 신뢰성 게이트를 코드/CI 수준으로 고정.
- 포함 범위:
  - CI 파이프라인에 API smoke + desktop doctor test + UI regression 연결
  - readiness/health 실패 케이스 표준화, 에러코드/힌트 정합화
  - migration/check gate 문서-실행 동기화
- 제외 범위:
  - provider 확장
  - UI 대규모 리디자인
- 선행 의존성: 현재 RC 브랜치 merge 완료
- 완료 기준:
  - PR마다 핵심 gate 자동 검증
  - 실패 시 원인 카테고리(backend/db/ollama/qdrant/upload/migration) 식별 가능
- 예상 리스크:
  - CI 환경별 의존성 편차
  - flaky integration 테스트

## B. `postmerge/desktop-packaging-runtime-ops`
- 목적: desktop 배포/실행 시 backend 별도 프로세스 운영 공백 축소.
- 포함 범위:
  - packaged desktop 운영 가이드(systemd/service wrapper 예시)
  - startup ordering 및 장애 복구 절차 강화
  - doctor 출력과 운영 runbook 자동 링크/참조 개선
- 제외 범위:
  - orchestration 로직 변경
- 선행 의존성: A 브랜치의 gate 안정화 권장
- 완료 기준:
  - 신규 개발자/운영자가 문서만으로 desktop+backend 실행 가능
  - 장애 재기동 순서가 runbook에 검증된 형태로 반영
- 예상 리스크:
  - OS별 운영 방식 편차

## C. `postmerge/provider-abstraction-phase1`
- 목적: Ollama 단일 가정 완화(설계 중심, 구현 최소).
- 포함 범위:
  - provider interface 정리(현재 Ollama adapter와 호환)
  - role routing에서 provider capability contract 초안
- 제외 범위:
  - 신규 provider 실제 연결 구현
- 선행 의존성: A 완료
- 완료 기준:
  - provider abstraction 설계 문서 + 최소 refactor PR
- 예상 리스크:
  - 추상화 과잉으로 인한 복잡도 증가

## D. `postmerge/perf-large-timeline-and-assets`
- 목적: 대규모 데이터에서 UX/perf 체감 개선.
- 포함 범위:
  - timeline virtualization
  - retrieval preview/diagnostics 패널 lazy rendering
  - 대용량 asset 처리 UI 피드백 개선
- 제외 범위:
  - backend 아키텍처 대수술
- 선행 의존성: A, B 권장
- 완료 기준:
  - 긴 대화/큰 자산에서도 UI 응답성 악화 완화
- 예상 리스크:
  - regression 리스크(기존 렌더링 흐름)

## E. `postmerge/observability-and-ops`
- 목적: 운영 관측성과 대응 속도 개선.
- 포함 범위:
  - structured logging/trace-id 표준화
  - run 실패 taxonomy와 운영 대시보드 지표 정의
  - release health report 템플릿
- 제외 범위:
  - 제품 기능 확대
- 선행 의존성: A
- 완료 기준:
  - 장애 분석 시간 단축(로그 기준)
- 예상 리스크:
  - 과도한 로그 노이즈/비용

## 4) Prioritized backlog

### Immediate next
1. CI gate 고정: API smoke + doctor + 핵심 UI regression.
2. readiness/health/doctor failure taxonomy 통일.
3. runbook 절차 기반 실제 dry-run(온보딩 관점) 수행.

### Near-term
1. desktop packaging/runtime 운영 시나리오 정리.
2. 긴 타임라인/대용량 asset UX 성능 개선 1차.
3. observability 최소 표준(로그 필드/실패 분류) 적용.

### Later
1. provider abstraction phase2 (실 provider 추가 전 단계).
2. production deployment profile(auth/secret/backup) 정교화.
3. 멀티 프로세스 lifecycle orchestration 고도화.

## 5) Dependency order

1. A (`production-hardening-gates`)
2. B (`desktop-packaging-runtime-ops`)
3. D (`perf-large-timeline-and-assets`) + E (`observability-and-ops`) 병렬 가능
4. C (`provider-abstraction-phase1`)은 A 이후 시작

## 6) Recommended execution sequence

1. Merge current RC branch
2. `postmerge/production-hardening-gates` 착수 (첫 브랜치)
3. Gate 안정화 후 packaging/runtime ops 브랜치 진행
4. 이후 perf/observability 병행
5. provider abstraction은 설계-안정화 이후 시작

## 7) Scope boundary (already done vs next)

### 이미 해결된 것 (현재 RC)
- orchestration, approval flow, role mapping, retrieval, doctor, runbook, smoke baseline.

### 후속 브랜치에서 다룰 것
- 운영 자동화/가시성/성능/확장성(추상화) 계층.

### 지금 브랜치에서 굳이 하지 않은 이유
- RC 목표는 기능 확장보다 release 판단 가능 상태 확보였기 때문.
- 아키텍처/성능/운영 자동화는 별도 브랜치로 분리해야 리스크 관리가 가능.
