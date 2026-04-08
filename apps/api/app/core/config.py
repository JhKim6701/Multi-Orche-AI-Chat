from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "multi-orche-ai-chat-api"
    env: Literal["dev", "prod", "desktop"] = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/multi_orche"
    ollama_base_url: str = "http://localhost:11434"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "moac_asset_chunks"

    data_root: str | None = None
    upload_root: str | None = None

    max_upload_mb: int = 25
    auto_create_tables: bool = True

    ollama_embedding_model: str = "nomic-embed-text"
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 120
    rag_retrieve_top_k: int = 8
    rag_pack_max_chars: int = 2600
    ocr_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOAC_", extra="ignore")

    @model_validator(mode="after")
    def _normalize_paths(self) -> "Settings":
        if self.data_root:
            base = Path(self.data_root).expanduser()
        elif self.env == "desktop":
            base = Path.home() / ".multi-orche-ai-chat" / "data"
        else:
            base = Path.cwd() / "data"
        base = base.resolve()
        base.mkdir(parents=True, exist_ok=True)

        if self.upload_root:
            upload = Path(self.upload_root).expanduser().resolve()
        else:
            upload = base / "uploads"
        upload.mkdir(parents=True, exist_ok=True)

        db_url = self.database_url
        if db_url.startswith("sqlite") and "///./" in db_url:
            filename = db_url.split("///./", 1)[1]
            db_url = f"sqlite+pysqlite:///{(base / filename).resolve()}"

        object.__setattr__(self, "data_root", str(base))
        object.__setattr__(self, "upload_root", str(upload))
        object.__setattr__(self, "database_url", db_url)
        return self

    @property
    def runtime_state_file(self) -> Path:
        return Path(self.data_root) / "runtime_state.json"


settings = Settings()
