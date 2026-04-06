from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import assets, chats, messages, models, orchestration, projects, segments, system
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.services.failure_taxonomy import classify_failure, recovery_hint

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
    category = classify_failure(str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": category,
                "message": str(exc),
                "recovery_hint": recovery_hint(category),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "request failed"
    category = classify_failure(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": category if category != "runtime_error" else f"http_{exc.status_code}",
                "message": detail,
                "recovery_hint": recovery_hint(category),
            },
            "detail": detail,
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
