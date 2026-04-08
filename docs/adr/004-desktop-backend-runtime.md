# ADR-004: Desktop Runtime Packaging Strategy

## Status
Accepted (phase-1)

## Context
현재 앱은 FastAPI 백엔드 + React/Tauri 프론트로 구성되어 있으며, Ollama/Qdrant 의존성이 로컬 서비스로 분리되어 있다.

## Decision
- phase-1 배포는 **Tauri는 프론트만 패키징**하고, 백엔드는 별도 로컬 서비스로 실행한다.
- 데스크톱 런타임에서는 `MOAC_ENV=desktop`을 권장하며 데이터 루트는 사용자 홈 기준 경로(`~/.multi-orche-ai-chat/data`)를 기본값으로 사용한다.
- 앱 시작 전 `npm run doctor`로 API health/dependency 상태를 점검한다.

## Consequences
- 장점: 배포 단순화, 백엔드/모델 서비스 업데이트 분리, 운영 진단 용이.
- 단점: 사용자에게 백엔드/Ollama/Qdrant 사전 실행 안내가 필요.
- 후속: installer/signing, bundled backend, auto-start 보조 서비스는 차기 단계로 분리.
