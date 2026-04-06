from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "multi-orche-ai-chat-api"
    env: str = "dev"
    database_url: str = "sqlite+pysqlite:///./multi_orche.db"
    ollama_base_url: str = "http://localhost:11434"
    upload_root: str = "./data"
    max_upload_mb: int = 25
    auto_create_tables: bool = True
    ollama_embedding_model: str = "nomic-embed-text"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "moac_asset_chunks"
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 120
    rag_retrieve_top_k: int = 8
    rag_pack_max_chars: int = 2600

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOAC_")


settings = Settings()
