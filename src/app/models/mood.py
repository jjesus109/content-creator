from datetime import date, datetime
from pydantic import BaseModel, Field
import uuid


class MoodProfile(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime
    week_start: date
    profile_text: str
