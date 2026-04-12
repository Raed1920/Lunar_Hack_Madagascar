from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


SupportedLanguage = Literal["en", "fr", "ar"]
DecisionPriority = Literal["low", "medium", "high"]


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Stable user identifier")
    session_id: str = Field(..., description="Conversation session identifier")
    message: str = Field(..., min_length=1, description="Latest user message")
    language: Optional[SupportedLanguage] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntentAnalysis(BaseModel):
    intent: str = "diagnose"
    domain: str = "general"
    confidence: float = 0.5
    concern_area: str = "general_management"
    urgency: str = "medium"
    requires_rag: bool = False
    rationale: str = ""


class SchemaBlueprint(BaseModel):
    required_fields: List[str] = Field(default_factory=list)
    field_descriptions: Dict[str, str] = Field(default_factory=dict)
    rationale: str = ""


class QualificationResult(BaseModel):
    updated_profile: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None


class RAGChunk(BaseModel):
    text: str
    score: float = 0.0
    source: str = "unknown"


class RAGResult(BaseModel):
    factual_response: str = ""
    citations: List[str] = Field(default_factory=list)
    grounded: bool = True
    confidence: str = "medium"
    uncertainty: str = ""


class DecisionOption(BaseModel):
    title: str = ""
    summary: str = ""
    tradeoff: str = ""


class RecommendationResult(BaseModel):
    recommended_strategy: str = ""
    actions: List[str] = Field(default_factory=list)
    expected_impact: str = ""
    decision_options: List[DecisionOption] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class DecisionResult(BaseModel):
    action: str = "Start with the highest-impact action"
    priority: DecisionPriority = "medium"
    justification: str = ""
    steps: List[str] = Field(default_factory=list)
    priority_score: int = 50


class ResponseDraft(BaseModel):
    response: str = ""
    next_question: Optional[str] = None


class FinalizationResult(BaseModel):
    recommendation: RecommendationResult = Field(default_factory=RecommendationResult)
    decision: DecisionResult = Field(default_factory=DecisionResult)
    response: ResponseDraft = Field(default_factory=ResponseDraft)


class RouteDecision(BaseModel):
    intent: str = "analysis"
    requires_rag: bool = False
    risk_level: str = "medium"
    confidence: float = 0.6
    rationale: str = "heuristic router"


class UnifiedRecommendation(BaseModel):
    strategy: str = ""
    actions: List[str] = Field(default_factory=list)


class UnifiedGenerationOutput(BaseModel):
    response: str = ""
    recommendation: UnifiedRecommendation = Field(default_factory=UnifiedRecommendation)
    risk_level: str = "medium"
    requires_follow_up: bool = False
    next_question: str = ""


class StructuredOutput(BaseModel):
    business_type: str = "unknown"
    need: str = ""
    recommended_strategy: str = ""
    estimated_impact: str = ""
    cta: str = "Start implementation"
    lead_score: int = 0
    concern_area: str = "general_management"
    urgency: str = "medium"
    priority_actions: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    language: SupportedLanguage
    structured: StructuredOutput
    user_profile: Dict[str, Any] = Field(default_factory=dict)
    rag_sources: List[str] = Field(default_factory=list)
    follow_up_email: str = ""
    next_question: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    last_message: str
    last_role: str
    last_created_at: str
    message_count: int = 0


class SessionMessage(BaseModel):
    role: str
    message: str
    created_at: str
