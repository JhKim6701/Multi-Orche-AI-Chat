from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(models.router)
app.include_router(assets.router)
app.include_router(segments.router)
app.include_router(orchestration.router)
