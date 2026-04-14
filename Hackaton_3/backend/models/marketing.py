from pydantic import BaseModel, Field

class StrategyPlan(BaseModel):
    positioning: str
    target_psychology: str
    market_opportunity: str
    messaging_pillars: list[str] = Field(default_factory=list)
    tone_recommendation: str
    channel_priorities: list[str] = Field(default_factory=list)
    timeline_summary: str
    risk_notes: list[str] = Field(default_factory=list)


class CriticResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    score: float = 0.0
