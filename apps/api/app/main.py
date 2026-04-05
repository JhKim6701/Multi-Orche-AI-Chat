from fastapi import FastAPI

from app.api.routers import assets, chats, messages, models, orchestration, projects, system
from app.db.base import Base
from app.db.session import engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="multi-orche-ai-chat-api")

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(models.router)
app.include_router(assets.router)
app.include_router(orchestration.router)
