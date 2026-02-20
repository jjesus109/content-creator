from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid


class PipelineRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime
    status: Literal["running", "completed", "failed", "rejected"]
    mood_profile: Optional[str] = None
    error_message: Optional[str] = None
    cost_usd: Decimal = Decimal("0")
