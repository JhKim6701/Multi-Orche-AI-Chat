from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import assets, chats, messages, models, orchestration, projects, segments, system
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title="multi-orche-ai-chat-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.auto_create_tables and settings.env == "dev":
    Base.metadata.create_all(bind=engine)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "runtime_error",
                "message": str(exc),
                "recovery_hint": "환경변수/저장경로/의존성(Ollama,Qdrant)을 확인 후 다시 시도하세요.",
            }
        },
    )


@app.on_event("startup")
def startup_checks():
    Path(settings.upload_root).mkdir(parents=True, exist_ok=True)
    Path(settings.data_root).mkdir(parents=True, exist_ok=True)

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(models.router)
app.include_router(assets.router)
app.include_router(segments.router)
app.include_router(orchestration.router)
