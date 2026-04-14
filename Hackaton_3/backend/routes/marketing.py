from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from ..config import get_settings
from ..models.schemas import (
    AnalyzeMarketingResponse,
    CampaignDetailsResponse,
    ChatRequest,
    ChatResponse,
    CreativeBriefRequest,
    CreativeBriefResponse,
    FeedbackRequest,
    FeedbackResponse,
    GenerateMarketingRequest,
    GenerateMarketingResponse,
    RefineMarketingRequest,
    RefineMarketingResponse,
    SignalsResponse,
    SolutionItem,
)
from ..models.shared import HealthResponse
from ..services.marketing_service import MarketingService, get_marketing_service


router = APIRouter(prefix="/v1/marketing", tags=["marketing"])
QUALITY_TEST_PAGE = Path(__file__).resolve().parent.parent / "static" / "quality_chat_test.html"


@router.get("/health", response_model=HealthResponse)
async def health(service: MarketingService = Depends(get_marketing_service)) -> HealthResponse:
    status = await service.health()
    return HealthResponse(
        status=status["status"],
        database=status["database"],
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/analyze", response_model=AnalyzeMarketingResponse)
async def analyze(
    request: GenerateMarketingRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> AnalyzeMarketingResponse:
    return await service.analyze(request)


@router.post("/solutions", response_model=list[SolutionItem])
async def solutions(
    request: GenerateMarketingRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> list[SolutionItem]:
    return await service.generate_solutions_only(request)


@router.post("/generate", response_model=GenerateMarketingResponse)
async def generate(
    request: GenerateMarketingRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> GenerateMarketingResponse:
    return await service.generate(request)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> ChatResponse:
    return await service.chat(request)


@router.post("/generate/stream")
async def generate_stream(
    request: GenerateMarketingRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> StreamingResponse:
    async def _stream() -> object:
        async for event in service.generate_stream(request):
            yield f"{json.dumps(event, ensure_ascii=True)}\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.post("/refine", response_model=RefineMarketingResponse)
async def refine(
    request: RefineMarketingRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> RefineMarketingResponse:
    return await service.refine(request)


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    request: FeedbackRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> FeedbackResponse:
    return await service.record_feedback(request)


@router.get("/campaign/{campaign_id}", response_model=CampaignDetailsResponse)
async def campaign_details(
    campaign_id: UUID,
    service: MarketingService = Depends(get_marketing_service),
) -> CampaignDetailsResponse:
    campaign = await service.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/signals", response_model=SignalsResponse)
async def signals(
    workspace_id: UUID | None = Query(default=None),
    region: str | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    service: MarketingService = Depends(get_marketing_service),
) -> SignalsResponse:
    settings = get_settings()
    resolved_workspace = workspace_id or UUID(settings.default_workspace_id)
    return await service.get_signals(resolved_workspace, region, signal_type)


@router.get("/ops/n8n-impact")
async def n8n_impact(
    workspace_id: UUID | None = Query(default=None),
    service: MarketingService = Depends(get_marketing_service),
) -> dict[str, Any]:
    settings = get_settings()
    resolved_workspace = workspace_id or UUID(settings.default_workspace_id)
    return await service.get_n8n_impact(resolved_workspace)


@router.post("/ops/workflows/trigger")
async def trigger_workflows(
    workspace_id: UUID | None = Query(default=None),
    run_signal: bool = Query(default=True),
    run_learning: bool = Query(default=True),
    run_publish: bool = Query(default=True),
    service: MarketingService = Depends(get_marketing_service),
) -> dict[str, Any]:
    settings = get_settings()
    resolved_workspace = workspace_id or UUID(settings.default_workspace_id)
    return await service.trigger_workflows(
        resolved_workspace,
        run_signal=run_signal,
        run_learning=run_learning,
        run_publish=run_publish,
    )


@router.post("/media/generate-creative-brief", response_model=CreativeBriefResponse)
async def generate_creative_brief(
    request: CreativeBriefRequest,
    service: MarketingService = Depends(get_marketing_service),
) -> CreativeBriefResponse:
    return await service.generate_creative_brief(request)


@router.get("/ui/quality-test", include_in_schema=False)
async def quality_test_ui() -> FileResponse:
    if not QUALITY_TEST_PAGE.exists():
        raise HTTPException(status_code=404, detail="Quality test page not found")
    return FileResponse(QUALITY_TEST_PAGE)
