from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class CircuitBreakerState(BaseModel):
    id: int = 1  # singleton row — always ID=1
    current_day_cost: Decimal = Decimal("0")
    current_day_attempts: int = 0
    tripped_at: Optional[datetime] = None
    last_trip_at: Optional[datetime] = None   # for rolling 7-day escalation window
    weekly_trip_count: int = 0
    week_start: date
    updated_at: datetime
