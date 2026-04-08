# Architecture Overview

- Desktop shell: Tauri v2 (planned in `apps/desktop/src-tauri`)
- UI: React + TypeScript + Zustand + TanStack Query + resizable panels
- API: FastAPI + SQLAlchemy 2.x + Alembic
- Runtime: host-installed Ollama via HTTP API
- Storage: PostgreSQL/Qdrant/local filesystem (`data/`)
- Orchestration: LangGraph-compatible run/step persistence skeleton
