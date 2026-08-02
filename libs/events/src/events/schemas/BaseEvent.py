from pydantic import BaseModel, Field
from datetime import datetime, timezone

from typing import Optional

class BaseEvent(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    key: Optional[str] = None
