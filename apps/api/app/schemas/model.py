from datetime import datetime

from pydantic import BaseModel


class ModelRegistryOut(BaseModel):
    id: int
    model_name: str
    provider: str
    downloaded: bool
    enabled: bool
    supports_vision: bool
    supports_tools: bool
    supports_embeddings: bool
    supports_reasoning: bool
    preferred_roles_json: list[str] | None
    sort_order: int
    last_seen_at: datetime | None

    class Config:
        from_attributes = True


class ModelToggle(BaseModel):
    enabled: bool


class ModelSortUpdate(BaseModel):
    sort_order: int
