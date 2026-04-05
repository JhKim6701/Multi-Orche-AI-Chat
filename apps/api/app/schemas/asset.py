from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AssetOut(BaseModel):
    id: int
    project_id: int
    chat_thread_id: int
    message_id: int | None
    source_type: str
    asset_type: str
    mime_type: str
    original_filename: str
    stored_path: str
    derived_metadata_json: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True
