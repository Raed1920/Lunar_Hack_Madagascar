from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .marketing import StrategyPlan


ObjectiveType = Literal["awareness", "engagement", "leads", "sales"]
LanguageMode = Literal["fr", "ar", "bilingual", "auto"]
ToneType = Literal["professional", "fun", "storytelling"]


class AudienceInput(BaseModel):
    age_range: str | None = None
    location: str | None = None
    interests: list[str] = Field(default_factory=list)
    segment: str | None = None


class BudgetConstraint(BaseModel):
    low: float | None = None
    high: float | None = None
    currency: str = "TND"


class GenerateMarketingRequest(BaseModel):
    workspace_id: UUID
    product_name: str
    product_description: str | None = None
    product_category: str | None = None
    objective: ObjectiveType
    campaign_timeline: str | None = None
    audience: AudienceInput = Field(default_factory=AudienceInput)
    budget_constraint: BudgetConstraint = Field(default_factory=BudgetConstraint)
    language_preference: LanguageMode = "auto"
    tone_preference: ToneType | None = None
    constraints: str | None = None


class AnalyzeMarketingResponse(BaseModel):
    strategy: StrategyPlan
    signals_used_count: int


class SolutionExecution(BaseModel):
    content_format: str
    message: str
    assets_needed: list[str] = Field(default_factory=list)
    timeline: str
    frequency: str
    posting_windows: list[dict[str, str]] = Field(default_factory=list)
    image_prompt: str | None = None
    exact_copy: str | None = None
    text_overlay: str | None = None
    cta_text: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    production_steps: list[str] = Field(default_factory=list)


class SolutionBudget(BaseModel):
    total_low: float
    total_high: float
    currency: str = "TND"
    breakdown: dict[str, float] = Field(default_factory=dict)


class SolutionOutcomes(BaseModel):
    reach: str
    engagement_rate: str
    conversion_assumption: str
    roi_estimate: str


class SolutionItem(BaseModel):
    id: str
    index: int
    channel: str
    solution_name: str
    description: str
    execution: SolutionExecution
    budget: SolutionBudget
    expected_outcomes: SolutionOutcomes
    confidence_score: float
    reasoning: str
    signals_used: list[str] = Field(default_factory=list)
    risk_level: str


class PortfolioSummary(BaseModel):
    total_solutions: int
    channels_covered: list[str] = Field(default_factory=list)
    budget_range: dict[str, float] = Field(default_factory=dict)
    recommended_quick_wins: list[str] = Field(default_factory=list)
    recommended_scale_plays: list[str] = Field(default_factory=list)


class MarketSignalItem(BaseModel):
    id: str | None = None
    signal: str
    type: str
    impact: str


class StrategicOption(BaseModel):
    option_key: str
    title: str
    category: str
    why_it_fits: str
    expected_impact: str
    effort_level: str
    budget_range_tnd: dict[str, float] = Field(default_factory=dict)
    recommended: bool = False
    first_actions: list[str] = Field(default_factory=list)


class ActionPlanDay(BaseModel):
    day: int
    focus: str
    action: str
    expected_output: str


class GenerateMarketingResponse(BaseModel):
    campaign_id: UUID
    strategy: StrategyPlan
    solutions: list[SolutionItem] = Field(default_factory=list)
    portfolio_summary: PortfolioSummary
    market_signals_used: list[MarketSignalItem] = Field(default_factory=list)
    assistant_explanation: str
    strategic_options: list[StrategicOption] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    recommended_path: str
    next_7_days_plan: list[ActionPlanDay] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    confidence_overall: float
    generation_latency_ms: int
    created_at: datetime


class ChatImageInput(BaseModel):
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    notes: str | None = None
    data_base64: str | None = None
    metadata: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    message: str
    workspace_id: UUID | None = None
    images: list[ChatImageInput] = Field(default_factory=list)
    image_pack: list[ChatImageInput] = Field(default_factory=list)
    language_preference: LanguageMode | None = None
    tone_preference: ToneType | None = None

    @model_validator(mode="after")
    def merge_legacy_image_pack(self) -> "ChatRequest":
        if self.image_pack:
            if self.images:
                self.images = [*self.images, *self.image_pack]
            else:
                self.images = list(self.image_pack)
        return self


class ChatImageInsight(BaseModel):
    filename: str
    quality_score: float
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    priority: str = "medium"


class ChatResponse(BaseModel):
    status: Literal["generated", "question_asked"] = "generated"
    campaign_id: UUID | None = None
    assistant_message: str
    assumptions_used: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    visual_insights: list[ChatImageInsight] = Field(default_factory=list)
    result: GenerateMarketingResponse | None = None


class CreativeBriefRequest(BaseModel):
    workspace_id: UUID
    campaign_id: UUID | None = None
    product_name: str
    objective: ObjectiveType
    channel: str = "social_media"
    audience: AudienceInput = Field(default_factory=AudienceInput)
    language_preference: LanguageMode = "auto"
    tone_preference: ToneType | None = None
    style_constraints: list[str] = Field(default_factory=list)
    reference_notes: str | None = None


class CreativeBriefResponse(BaseModel):
    campaign_id: UUID | None = None
    objective: str
    channel: str
    image_prompt: str
    canva_template_suggestion: str
    color_palette: list[str] = Field(default_factory=list)
    text_overlay: str
    do_not_include: list[str] = Field(default_factory=list)
    recommended_aspect_ratio: str = "4:5"
    rationale: str


class GenerateStreamEvent(BaseModel):
    status: str
    step: str
    data: dict[str, Any] | None = None
    timestamp: datetime


class RefineMarketingRequest(BaseModel):
    campaign_id: UUID
    refinement_instruction: str
    updated_budget_constraint: BudgetConstraint | None = None


class RefineMarketingResponse(BaseModel):
    campaign_id: UUID
    refinement_id: str
    removed_solutions: list[str] = Field(default_factory=list)
    new_solutions: list[SolutionItem] = Field(default_factory=list)
    modified_solutions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class FeedbackPerformance(BaseModel):
    impressions: int | None = None
    clicks: int | None = None
    conversions: int | None = None
    engagement_count: int | None = None


class FeedbackRequest(BaseModel):
    campaign_id: UUID
    solution_id: str
    feedback_type: str = "selected"
    selected: bool = True
    edited_content: str | None = None
    published: bool = False
    published_url: str | None = None
    performance: FeedbackPerformance | None = None
    user_notes: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    campaign_id: UUID
    solution_id: str
    learning_update: dict[str, Any]
    created_at: datetime


class SignalsResponse(BaseModel):
    signals: list[dict[str, Any]] = Field(default_factory=list)
    count: int
    fetched_at: datetime


class CampaignDetailsResponse(BaseModel):
    campaign_id: UUID
    workspace_id: UUID
    status: str
    brief: dict[str, Any]
    strategy: dict[str, Any] | None = None
    solutions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
