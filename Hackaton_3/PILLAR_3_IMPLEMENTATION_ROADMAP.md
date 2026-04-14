# Pillar 3: Marketing AI Assistant - Step-by-Step Implementation

## Vision Expansion
**Output Scope**: Not just social media posts, but a **complete marketing solution portfolio** with:
- Multiple channels (social, email, SMS, events, partnerships, paid, content, etc.)
- Strategy + execution for each
- Budget estimation with ROI assumptions
- Confidence/risk scoring
- Why this solution fits the business + market
- Multimodal assistant input (text + user image)
- Visual insights from uploaded assets (branding, composition, quality, CTA clarity)
- AI-generated creatives (images now, video storyboard now, full video rendering optional)

## T-1h Status Snapshot (April 12, 2026)
- Core generation is stable: strategy + portfolio + critic + persistence are operational.
- Chat flow is now multi-agent orchestrated:
  - Brief Extraction Agent (message -> structured brief)
  - Strategy/Solutions Agents (portfolio generation)
  - Vision Critic Agent (AI image review with provider fallback + heuristic fallback)
  - Clarification Agent (asks up to 3 follow-up questions when context is missing)
- Payload compatibility is preserved (`images` and legacy `image_pack` accepted).
- Quality test UI supports real image payloads for AI vision analysis.
- Validation status: backend tests and smoke scripts are green.

## Free-First Technology Policy

### Mandatory baseline (100% free)
- Backend: FastAPI + Pydantic + Uvicorn (open source)
- Database: PostgreSQL in Docker (local)
- Automation: n8n self-hosted (local Docker)
- AI fallback path: deterministic/rule-based generation always available with no external API keys
- Data enrichment: free/public sources (Google Trends via scraping/pytrends, Open-Meteo, public event calendars)

### Optional free-tier add-ons (quota-limited)
- LLM inference: Groq free tier, Gemini free tier
- Media/vision APIs: Hugging Face free tier or similar quota-limited providers
- Hosted n8n: cloud.n8n.io free tier (instead of self-hosting)

### Non-negotiable rule
- The app must run end-to-end in local mode with zero paid services and zero required subscriptions.

## Delivery Priority (MVP vs Optional)

### MVP (must ship first)
- Local PostgreSQL schema + seed + smoke test (`db_up` + `db_smoke_test`)
- Core endpoints: `/generate`, `/refine`, `/feedback`, `/campaign/{id}`, `/signals`
- Core logic: Strategy Planner + Solutions Generator + Budget Estimator + Critic Validator
- Portfolio output with budgets and reasoning (5-8 solutions, diverse channels)
- One n8n core workflow minimum: Market Signal Enricher (Workflow 1)
- Demo readiness: seeded realistic data + stable live script

### Optional Tier 1 (only after MVP is green)
- Unified multimodal chat endpoint (`/chat`) accepting text + image metadata
- Visual analyzer endpoint (`/media/analyze`) returning structured creative insights
- Image generation endpoint (`/media/generate-image`) with persisted asset metadata
- n8n Campaign Ops Pipeline + Learning Loop (Workflows 2 and 3)

### Optional Tier 2 (stretch)
- Video storyboard endpoint (`/media/generate-video-plan`)
- n8n Creative Media Pipeline + Media Publish Scheduler (Workflows 4 and 5)
- Full video rendering integration (async, provider-dependent)

### Kill-switch rules (to avoid over-scoping)
- If MVP tests are not green by T-8h: freeze all multimodal work.
- If `/generate` latency exceeds demo tolerance, disable image/video generation and keep text strategy flow.
- If media providers are unstable, keep storyboard-only output and skip render.
- Never block demo path on optional workflows.

---

## PHASE 1: Database Schema & Data Model
### Step 1: Create local PostgreSQL tables
- `market_signals` — trends, events, seasonality, competitor moves
- `marketing_solutions_library` — pre-built solution templates with budget ranges
- `campaign_briefs` — user input (product, audience, objective, budget, constraints)
- `campaigns` — top-level campaign entity linking brief, strategy, and solutions
- `campaign_strategies` — AI-generated strategy (positioning, tone, channels, timeline)
- `campaign_solutions` — generated portfolio (multiple channels + budgets + reasoning)
- `campaign_feedback` — user choice, edits, performance feedback
- `brand_memory` — workspace preferences, winning patterns, constraints
- `chat_sessions` and `chat_messages` — conversation memory for marketing assistant
- `media_assets` — uploaded image metadata and storage references
- `visual_insights` — extracted insights from user images and generated creatives
- `generated_media` — generated images and optional video outputs/storyboards

### Step 2: Design data schemas (DDL)
- Write exact SQL for all tables
- Add indexes for query performance
- Add constraints for data integrity
- Add `pgcrypto` extension for UUID generation
- Test DB startup using Docker (`scripts/db_up.ps1`) and validate seed data

---

## PHASE 2: FastAPI Backend Architecture
### Step 3: Set up FastAPI project structure
```
backend/
├── main.py
├── config.py (env vars, LLM router, n8n config)
├── database.py (PostgreSQL client, connection pool)
├── models/
│   ├── schemas.py (Pydantic request/response models)
│   ├── marketing.py (domain models)
│   └── shared.py (workspace, auth, pagination)
├── services/
│   ├── marketing_service.py (main orchestration)
│   ├── strategy_planner.py (LLM strategy step)
│   ├── solutions_generator.py (LLM solutions step)
│   ├── budget_estimator.py (logic for budget calc)
│   ├── critic_validator.py (quality gates)
│   ├── market_signals_repo.py (fetch signals from DB)
│   ├── multimodal_gateway.py (text+image request orchestration)
│   ├── visual_analyzer.py (vision insights extraction)
│   ├── image_generator.py (creative image generation)
│   └── video_planner.py (video storyboard/script generation)
├── routes/
│   └── marketing.py (endpoints)
├── prompts/
│   ├── strategy_v1.txt
│   ├── solutions_v1.txt
│   ├── critic_v1.txt
│   ├── visual_analyzer_v1.txt
│   ├── image_generator_v1.txt
│   └── video_planner_v1.txt
└── tests/
    └── test_marketing.py
```

### Step 4: Define FastAPI endpoint contracts
- `POST /v1/marketing/analyze` (receive brief, return strategy options)
- `POST /v1/marketing/solutions` (receive strategy, return portfolio)
- `POST /v1/marketing/generate` (one-shot: brief → strategy + solutions)
- `POST /v1/marketing/generate/stream` (NDJSON progress stream for live demo UX)
- `POST /v1/marketing/chat` (multimodal chat: text + optional image uploads)
- `POST /v1/marketing/media/analyze` (extract visual insights from uploaded image)
- `POST /v1/marketing/media/generate-creative-brief` (provider-free creative brief for Canva/designer handoff)
- `POST /v1/marketing/media/generate-image` (generate campaign visual from prompt)
- `POST /v1/marketing/media/generate-video-plan` (generate storyboard/script; render optional)
- `POST /v1/marketing/refine` (refine previous result)
- `POST /v1/marketing/feedback` (user selected solution, budget confirm, performance)
- `GET /v1/marketing/signals` (transparency endpoint: show signals influencing decisions)

### Step 5: Implement LLM Router abstraction
- Primary (default): local-free mode (no API key required)
- Optional fallback: Groq free tier
- Optional fallback 2: Gemini free tier
- Timeout handling and retry logic
- Token counting and cost estimation
- Route type support: `text_generation`, `vision_analysis`, `image_generation`, `video_storyboard`

---

## PHASE 3: Core Generation Logic
### Step 6: Build Strategy Planner (LLM step 1)
Input: campaign brief + market signals
Output: strategy object
```json
{
  "positioning": "why this product matters now",
  "target_psychology": "what audience fears/wants",
  "market_opportunity": "seasonal/trend/cultural angle",
  "messaging_pillars": ["pillar_1", "pillar_2", "pillar_3"],
  "tone_recommendation": "professional|fun|storytelling",
  "channel_priorities": ["primary", "secondary", "tertiary"],
  "timeline": "weeks to activate",
  "risk_notes": ["note_1", "note_2"]
}
```

### Step 7: Build Solutions Generator (LLM step 2)
Input: strategy + market signals + budget constraints
Output: solution portfolio (array of 5-8 solutions)

Each solution object:
```json
{
  "id": "solution_id",
  "channel": "social_media|email|sms|events|partnerships|paid_ads|content|influencer|pr|loyalty|other",
  "name": "Instagram Storytelling Campaign",
  "description": "Why this channel for your business",
  "execution": {
    "content_format": "video|carousel|static|story|reel",
    "message": "core message",
    "assets_needed": ["asset_1", "asset_2"],
    "timeline": "2 weeks to launch, 4 weeks active",
    "frequency": "3x per week"
  },
  "budget": {
    "total_budget_low": 0,
    "total_budget_high": 500,
    "currency": "TND",
    "breakdown": {
      "content_creation": 100,
      "ad_spend": 200,
      "management": 100,
      "tools": 50
    }
  },
  "expected_outcomes": {
    "reach": "10k-50k",
    "engagement_rate": "3-5%",
    "conversion_assumption": "1-2%",
    "roi_estimate": "3x-5x"
  },
  "confidence_score": 0.85,
  "reasoning": "Why this works for your audience + market right now",
  "signals_used": ["trend_1", "event_1", "season_1"],
  "risk_level": "low|medium|high"
}
```

### Step 7.1: Build Visual Insights Analyzer (Vision step)
Input: user image(s) + campaign objective + audience context
Output:
- Composition quality notes
- Product visibility score
- Brand consistency notes
- CTA/text readability notes (OCR-driven where possible)
- Action recommendations to improve creative performance

### Step 7.2: Build Creative Generation Layer
Input: strategy + solution + style constraints + reference image (optional)
Output:
- Structured creative brief (prompt + palette + overlay + exclusions)
- Generated image prompt
- Generated image asset (URL/path)
- Optional video storyboard/script and shot list
- Optional video rendering trigger (background)

### Step 8: Build Budget Estimator
Logic (not LLM):
- Base cost per channel (small table)
- Multiply by effort/complexity
- Add management overhead
- Regional adjustment (Tunisia-aware)
- Budget level multiplier (bootstrap vs growth vs scale)

### Step 9: Build Critic/Validator
Rules + LLM step to check:
- No duplicate solutions
- All channels align with objective
- Budgets realistic for MENA market
- No forbidden claims
- At least one solution is "quick win" (low budget)
- At least one is "ambitious" (higher ROI)
- Confidence scores reflect evidence actually used

### Step 10: Implement refine endpoint logic
- User provides feedback: "make email solution cheaper", "add TikTok option", etc.
- Store refinement request
- Re-run solutions generator with constraints
- Return delta (new solutions only)

### Step 10.1: Implement multimodal refine logic
- Accept feedback on generated visuals ("make it brighter", "less text", "more local style")
- Re-run image generation with refinement constraints
- Preserve version history of generated creative variants

---

## PHASE 4: Data Integration Layer
### Step 11: Implement market signals fetcher
- Query latest signals from DB
- Cache in memory (5 min TTL)
- Return signals and metadata for transparency

### Step 12: Implement brand memory reader
- Load workspace preferences (tone, language, banned words)
- Load historical winning patterns
- Load budget history

### Step 13: Implement persistence layer
- Save brief to `campaign_briefs`
- Save strategy to `campaign_strategies`
- Save solutions to `campaign_solutions`
- Emit event for n8n listen
- Save uploaded media metadata to `media_assets`
- Save vision analysis output to `visual_insights`
- Save generated assets/storyboards to `generated_media`

---

## PHASE 5: n8n Workflows Integration
### Step 14: Design n8n Workflow 1 — Market Signal Enricher
- Trigger: Cron every 3 hours
- Nodes:
  - `Cron`
  - `HTTP` nodes to fetch data:
    - Google Trends (pytrends/scraping)
    - Local event calendars (Tunisia, MENA)
    - Weather/season data (Open-Meteo free endpoint)
    - Reddit/X trending (optional)
  - `Function` node to normalize
  - Optional `LLM` node to summarize (only if free-tier quota exists)
  - `PostgreSQL` upsert to `market_signals`
- Output: Fresh signals in DB for next generation requests

### Step 15: Design n8n Workflow 2 — Campaign Ops Pipeline
- Trigger: Webhook when campaign generated
- Nodes:
  - `Webhook` (receive campaign_id)
  - `PostgreSQL` read campaign solutions
  - `IF` node: Is budget > workspace limit? Adjust.
  - `LLM` node: Brand safety check
  - `PostgreSQL` update status
  - Optional: `HTTP` to mock publish/schedule (for demo)
- Output: Solutions marked as "approved" + "ready to execute"

### Step 16: Design n8n Workflow 3 — Learning Loop
- Trigger: Daily cron
- Nodes:
  - `PostgreSQL` query yesterday's campaigns
  - `PostgreSQL` read mock performance metrics (for hackathon)
  - `Function` node: compute winning tone/channel combo
  - `PostgreSQL` upsert to `brand_memory`
  - `PostgreSQL` log learnings
- Output: Next generation gets smarter patterns

### Step 16.1: Design n8n Workflow 4 — Media Pipeline (optional but high impact)
- Trigger: Webhook after `/media/generate-image` or `/media/generate-video-plan`
- Nodes:
  - `Webhook`
  - `PostgreSQL` read campaign + media metadata
  - Optional external image/video generation API call (free-tier only)
  - `PostgreSQL` update `generated_media` status and links
  - Optional publish/schedule handoff
- Output: Generated creative assets tracked and ready for execution

---

## PHASE 6: Prompt Engineering
### Step 17: Write Strategy Planner Prompt
- Role: Market strategist for MENA SMEs
- Input schema specification
- Output schema (JSON only)
- Quality bar: cite market signals, include local context, explain why now
- Examples of good output

### Step 18: Write Solutions Generator Prompt
- Role: Marketing strategist+budget planner
- Input: strategy object + signals
- Output schema: array of solution objects
- Constraints: must include social, email, and 1-2 others per budget
- Quality: each solution has clear rationale, realistic budget, ROI logic

### Step 19: Write Critic Prompt
- Role: QA for marketing plans
- Input: portfolio of solutions
- Output: scores + list of issues (if any)
- Constraints: flag generic advice, flag impossible budgets, flag missing diversity

### Step 19.1: Write Visual Analyzer Prompt
- Role: Creative performance analyst
- Input: image + campaign context
- Output: structured visual diagnostics + improvement actions

### Step 19.2: Write Image/Video Prompt Templates
- Image prompt: composition, style, branding constraints, CTA placement
- Video prompt: storyboard, hook, sequence timing, voiceover script, captions

---

## PHASE 7: Testing & Validation
### Step 20: Unit test market signals fetcher
- Mock DB, confirm data shape
- Confirm caching works

### Step 21: Unit test budget estimator
- Test edge cases (very high budget, zero budget, regional multiplier)

### Step 22: Integration test: brief → strategy
- Pass test brief
- Confirm strategy object is valid JSON
- Confirm strategy cites signals
- Confirm tone matches objective

### Step 23: Integration test: strategy → solutions
- Pass strategy object
- Confirm 5-8 solutions returned
- Confirm each has budget breakdown
- Confirm no duplicates
- Confirm diversity (at least 3-4 different channels)

### Step 24: Integration test: critic validates portfolio
- Confirm low-risk solutions exist
- Confirm at least one under 100 TND
- Confirm at least one ambitious (500+ TND)

### Step 25: Integration test: refine works
- Generate solutions
- Refine with "add TikTok, remove email"
- Confirm new portfolio includes TikTok, excludes email

### Step 25.1: Integration test: multimodal path works
- Send text-only request to `/chat` and validate response schema
- Send text + image request to `/chat` and validate visual insights are returned
- Generate image and validate `generated_media` record is persisted
- Generate video storyboard and validate structured script/shot list output

---

## PHASE 8: Demo Readiness
### Step 26: Seed test data
- Create 3-5 fake businesses (e-commerce, food, agency)
- Create realistic briefs for each
- Pre-generate solutions so UI works instantly during demo
- Store in demo workspace

### Step 27: Build transparency UI helpers
- Endpoint to return signals used (for demo storytelling)
- Endpoint to return generation timeline (shows FastAPI fast + n8n enrichment)

### Step 28: Document API contracts (OpenAPI/Swagger)
- Auto-generate from FastAPI
- Export as Swagger JSON
- Share with frontend team for contract alignment

---

## PHASE 9: n8n Workflow Implementation
### Step 29: Build and test Workflow 1 (Enricher)
- Set up local n8n first (self-hosted free); use n8n cloud free tier only if needed
- Configure PostgreSQL connector
- Test full run: fetch → normalize → store
- Confirm data appears in market_signals table

### Step 30: Build and test Workflow 2 (Ops Pipeline)
- Set up webhook in FastAPI service
- Test full run: campaign generated → webhook fires → n8n processes → status updated

### Step 31: Build and test Workflow 3 (Learning)
- Create mock performance metrics
- Test full run: daily cron → read → compute → update memory

---

## PHASE 10: Integration & Merge
### Step 32: Package backend as Docker container
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 33: Document environment variables
- Optional API keys only (Groq/Gemini/Hugging Face). Not required in local-free mode.
- Optional local model endpoint (if added later, e.g., Ollama/LM Studio)
- PostgreSQL connection string
- n8n webhook URL
- Workspace defaults

### Step 34: Write README for backend
- Setup instructions
- How to run locally
- How to test endpoints
- How to integrate with Pillar 1/2

### Step 35: Hand off to frontend team
- Share Swagger/OpenAPI
- Share example request/response JSON
- Share demo data workspace ID

---

## PHASE 11: Demo Preparation
### Step 36: Record demo script
- Show multimodal brief: text + uploaded product image
- Show generated strategy (2-3 sec)
- Show portfolio of 7 solutions (email, social, events, influencer, ads, etc.)
- Show budget breakdown for each
- Show visual insights panel from uploaded image
- Show generated creative image variant and optional video storyboard
- Show n8n flow run history (proof of automation)

### Step 37: Prepare live demo fallback
- Have pre-computed results ready
- Load from demo workspace if API times out

### Step 38: Create pitch talking points
- "We don't just generate captions; we generate a full marketing strategy with budget options"
- "Every solution shows why it works for your market right now"
- "Backed by real market signals (trends, events, seasonality)"
- "Over time, learns your preferences and optimizes channel mix"

---

## Summary: Implementation Timeline

| Phase | Steps | Effort | Timeline |
|-------|-------|--------|----------|
| 1 | Schema design | 2 hours | Day 1 morning |
| 2 | FastAPI setup + contracts | 3 hours | Day 1 afternoon |
| 3 | Core generation logic | 6 hours | Day 1-2 |
| 4 | Data layer | 2 hours | Day 2 morning |
| 5 | n8n workflows design + build | 4 hours | Day 2 afternoon |
| 6 | Prompts | 2 hours | Day 2 |
| 7 | Testing | 3 hours | Day 2-3 |
| 8 | Demo prep | 2 hours | Day 3 morning |
| 9 | n8n testing | 2 hours | Day 3 |
| 10 | Integration + packaging | 3 hours | Day 3 afternoon |
| 11 | Demo script + fallbacks | 2 hours | Day 3 |

**Total: ~36-40 hours spread across 3 days (depending on optional video rendering).**

---

## Key Success Metrics

1. **By end of Phase 3**: Generate endpoint returns valid portfolio (not just posts).
2. **By end of Phase 5**: n8n Workflow 1 runs and populates market_signals.
3. **By end of Phase 7**: Multimodal path returns text+image insights and generated image output.
4. **By end of Phase 11**: Demo runs live without timeouts; judges see strategy → creative → execution → learning loop.

---

## What Makes This Different (Judge Appeal)

1. **Portfolio, not captions** — you solve the real marketing problem (which channel, what budget, what message).
2. **Evidence + reasoning** — every solution explains why, every budget cites assumptions.
3. **Learning loop** — next campaign gets smarter from previous feedback.
4. **Bilingual local market** — strategies adapt to Tunisia/MENA context automatically.
5. **Automation + creativity** — n8n enriches data while FastAPI creates strategy.

This positions Pillar 3 as a **true marketing decision engine**, not a content generator.
