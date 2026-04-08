from datetime import datetime

from pydantic import BaseModel


class Timestamped(BaseModel):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
