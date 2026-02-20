from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ContentHistory(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime
    pipeline_run_id: Optional[uuid.UUID] = None
    script_text: str
    topic_summary: Optional[str] = None
    embedding: Optional[list[float]] = None  # 1536 dims for text-embedding-3-small
    rejection_reason: Optional[str] = None
    published_at: Optional[datetime] = None
