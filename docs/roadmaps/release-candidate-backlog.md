# Release Candidate Backlog & Merge Decision Framework

## 1) Current release scope (this branch)

- FastAPI backend with orchestration, retrieval, role mapping, approval flow, artifacts, segmentation.
- Desktop UI with TopBar/ModelPanel/ChatPanel + doctor preflight + runbook.
- Smoke-oriented validation (`test_release_smoke.py`) and readiness/health/doctor checks.

이 범위는 **internal demo/review 용 release candidate**를 목표로 합니다.

## 2) Accepted limitations (intentionally not solved in this branch)

- Tauri bundle 단독으로는 완결 실행 불가(backend 별도 프로세스 필수).
- Ollama/Qdrant/DB 의존성 availability에 강하게 의존.
- doctor는 preflight 진단 도구이며 자동 복구 도구가 아님.
- 대용량 timeline / 대용량 asset 상황의 UX/perf는 후속 최적화 필요.

## 3) Post-merge priority queue (Next)

1. **CI 검증 안정화**
   - desktop vitest/tsc, api pytest를 설치된 CI 환경에서 항상 실행.
   - smoke test + doctor test 결과를 PR gate에 연결.
2. **Runtime resilience**
   - backend/Ollama/Qdrant 장애 케이스에서 재시도/타임아웃/표준 에러 코드 정합화.
3. **Desktop packaging ops**
   - backend 별도 프로세스 기동/감시 방법(systemd/service wrapper) 문서와 샘플 제공.
4. **UX follow-up**
   - 대화가 긴 경우 timeline virtualization, retrieval/diagnostics collapse 개선.

## 4) Long-term architecture follow-ups (Later)

- Provider abstraction 고도화(멀티 provider 정책 엔진 분리).
- Production deployment profile (auth, observability, backup/restore, secret management).
- Multi-process robustness (desktop app ↔ backend lifecycle orchestration).
- Performance tuning for large-context and large-asset workloads.

## 5) Merge/Release decision rubric

### Merge gate (must pass)
- health/readiness/doctor 체크가 문서와 일치.
- smoke test가 core flow를 검증(project/chat/manual/orchestration/approval/role-pref).
- known limitations가 README/runbook/backlog에 명시.

### Release gate (demo/review)
- preflight 준비 완료 및 demo 시나리오 재현 가능.
- blocker가 없고, non-blocker는 Next/Later로 분류되어 추적 가능.

## 6) Explicit technical debt left in branch

- Production-grade 운영 자동화 미완료(수동 절차 중심).
- 완전한 failure injection/chaos style test coverage 미구현.
- UI 성능 튜닝 및 accessibility 최종 점검은 후속 작업.
