"""Validated data models (pydantic)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1


class RawMarket(BaseModel):
    """Subset of Manifold's search-markets item that we rely on; extras ignored."""
    id: str
    question: str
    url: str
    probability: float = Field(ge=0, le=1)
    outcomeType: str
    volume: float = 0
    volume24Hours: float = 0
    totalLiquidity: float = 0
    closeTime: Optional[int] = None
    uniqueBettorCount: int = 0
    isResolved: bool = False


class Market(BaseModel):
    id: str
    question: str
    url: str
    category: str = "General"
    probability: float = Field(ge=0, le=1)
    volume: float = 0
    volume_24h: float = 0
    liquidity: float = 0
    bettors: int = 0
    close_time: Optional[datetime] = None
    p_24h: Optional[float] = Field(default=None, ge=0, le=1)
    p_7d: Optional[float] = Field(default=None, ge=0, le=1)
    history: list[tuple[int, float]] = Field(default_factory=list)  # (epoch ms, prob), 7 days

    @field_validator("history")
    @classmethod
    def _sorted(cls, v):
        return sorted(v)

    @property
    def change_24h(self) -> Optional[float]:
        return None if self.p_24h is None else self.probability - self.p_24h

    @property
    def change_7d(self) -> Optional[float]:
        return None if self.p_7d is None else self.probability - self.p_7d


class Snapshot(BaseModel):
    schema_version: int = SCHEMA_VERSION
    source: str = "manifold"
    generated_at: datetime
    markets: list[Market]

    @property
    def categories(self) -> list[str]:
        return sorted({m.category for m in self.markets})

    def age_hours(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        return (now - self.generated_at).total_seconds() / 3600
