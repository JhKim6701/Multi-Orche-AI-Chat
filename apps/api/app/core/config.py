from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "multi-orche-ai-chat-api"
    env: str = "dev"
    database_url: str = "sqlite+pysqlite:///./multi_orche.db"
    ollama_base_url: str = "http://localhost:11434"
    upload_root: str = "./data"
    max_upload_mb: int = 25

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOAC_")


settings = Settings()
