from datetime import datetime

from pydantic import BaseModel, Field


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
    metadata_json: dict | None
    sort_order: int
    last_seen_at: datetime | None

    class Config:
        from_attributes = True


class ModelToggle(BaseModel):
    enabled: bool


class ModelSortUpdate(BaseModel):
    sort_order: int


class RolePreferenceUpdate(BaseModel):
    preferred_model_names: list[str] = Field(default_factory=list)


class RolePreferenceOut(BaseModel):
    role: str
    preferred_model_names: list[str] = Field(default_factory=list)
    default_model_name: str | None = None
    fallback_model_names: list[str] = Field(default_factory=list)


class RoleCandidateOut(BaseModel):
    model_name: str
    downloaded: bool
    enabled: bool
    priority: int
