# Pillar 3 : Marketing AI Assistant — Team Handoff Summary

## What You're Building

A **Marketing Intelligence Engine** that turns any SME brief into a portfolio of actionable marketing solutions.

**Input**: "I want to promote my new artisan bread in Tunis for the next 2 weeks with budget 100-500 TND"

**Output**: 
- 7-8 solutions across different channels (social, email, WhatsApp, partnerships, paid ads, events, content)
- Each with strategy, execution plan, budget breakdown, and confidence score
- Ranked by effort/impact and immediate actionability
- All decisions explained using real market signals (trends, events, seasonality)

**Why this wins judges**:
1. Not just captions (boring).
2. Not just one channel (limited).
3. Portfolio + budgets (realistic for SMEs).
4. Evidence-based reasoning (credible).
5. Learns over time (intelligent).

## Cost Policy (Free-First)

1. Default architecture must be fully free and local: FastAPI + PostgreSQL + self-hosted n8n.
2. Generation must still work without any API key (local deterministic/rule-based fallback).
3. External APIs are optional and only from free-tier/quota-limited plans.
4. If free-tier quota is exhausted, app falls back to local mode and keeps core demo path alive.

## MVP vs Optional (Execution Guardrail)

### MVP (must complete before demo)
1. Local DB setup + schema + seed + smoke test.
2. Core API path: generate/refine/feedback/campaign/signals.
3. Portfolio generation with budgets + confidence + reasoning.
4. At least one n8n core workflow running (Market Signal Enricher).
5. Demo script with reliable seeded outputs.

### Optional Tier 1 (after MVP passes)
1. Multimodal chat (text + image metadata input).
2. Visual analyzer output from uploaded creative.
3. Image generation endpoint + generated asset persistence.
4. n8n Workflows 2 and 3.

### Optional Tier 2 (stretch)
1. Video storyboard endpoint.
2. n8n Workflows 4 and 5.
3. Full video rendering integration.

### Stop rules
1. If core tests fail, stop optional work and fix MVP only.
2. If media providers are unstable, keep storyboard-only and skip rendering.
3. Never let optional features block the main generate flow demo.

---

## What's Ready for Your Team

### 📋 Document 1: Implementation Roadmap (38 Steps)
**File**: `PILLAR_3_IMPLEMENTATION_ROADMAP.md`

11 phases covering:
- Database design
- FastAPI setup
- Core generation logic
- n8n workflows
- Testing
- Demo prep

**Timeline**: ~36-40 hours across 3 days (with optional multimodal extensions)

### 🗄️ Document 2: Database Schemas (Exact SQL)
**File**: `PILLAR_3_DATABASE_SCHEMA.md`

Core tables are now executable via local PostgreSQL init scripts:
- `market_signals` — trends/events/seasonality data
- `campaign_briefs` — user input
- `campaigns` — top-level campaign entity
- `campaign_strategies` — AI strategy
- `campaign_solutions` — generated portfolio
- `campaign_feedback` — user choices + performance
- `brand_memory` — learned patterns
- Indexes + constraints included

**Action**: run `./scripts/db_up.ps1` to initialize schema and seed data automatically.

### 🔌 Document 3: API Contracts (Full Examples)
**File**: `PILLAR_3_API_CONTRACTS.md`

11 implemented endpoints (9 core contracts + 2 quick-win reliability endpoints):
1. `POST /marketing/generate` — brief → strategy + portfolio
2. `POST /marketing/generate/stream` — progressive NDJSON generation stream
3. `POST /marketing/refine` — edit previous result
4. `GET /marketing/campaign/{id}` — retrieve campaign details
5. `POST /marketing/feedback` — log user action
6. `GET /marketing/signals` — transparency data
7. `POST /marketing/chat` — unified multimodal assistant (text + image)
8. `POST /marketing/media/analyze` — visual diagnostics
9. `POST /marketing/media/generate-creative-brief` — provider-free creative production brief
10. `POST /marketing/media/generate-image` — creative image variants
11. `POST /marketing/media/generate-video-plan` — storyboard/script generation

**Includes**: full request/response JSON examples, error codes, all fields.

### ⚙️ Document 4: n8n Workflows (Node-by-Node)
**File**: `PILLAR_3_N8N_WORKFLOWS.md`

5 workflows documented (3 core + 2 multimodal):

1. **Market Signal Enricher** (run every 3 hours)
   - Fetch trends, events, season data
   - Normalize and store in market_signals
   - Result: fresh context for generation

2. **Campaign Ops Pipeline** (trigger on generation)
   - Quality check solutions
   - Brand safety validation
   - Approval/rejection flow
   - Result: vetted solutions ready for action

3. **Learning Loop** (run daily)
   - Analyze yesterday's performance
   - Update brand_memory with winning patterns
   - Result: next generation is smarter

4. **Creative Media Pipeline** (triggered by media generation requests)
   - Generate/store image assets and optional video render jobs
   - Result: creative outputs tracked in generated_media

5. **Media Publish Scheduler** (cron/manual)
   - Publish approved media to channel adapters and log status
   - Result: generated creatives move from plan to execution

---

## How to Get Started (Right Now)

### Step 1: Set Up Backend (2 hours)
```bash
# Create FastAPI project
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install fastapi pydantic uvicorn python-dotenv

# Start local PostgreSQL and auto-run schema + seed SQL
powershell -ExecutionPolicy Bypass -File .\scripts\db_up.ps1

# Verify tables and recent logs
powershell -ExecutionPolicy Bypass -File .\scripts\db_status.ps1
```

### Step 2: Stub Out Endpoints (1 hour)
```python
# In main.py, create route handlers for all core + multimodal endpoints
# Use Pydantic models from PILLAR_3_API_CONTRACTS.md

@app.post("/v1/marketing/generate")
async def generate(brief: CampaignBrief):
    # TODO: implement
    return {"campaign_id": "stub"}
```

### Step 3: Implement Core Logic (4-5 hours)
Following PILLAR_3_IMPLEMENTATION_ROADMAP.md:
- Step 6: Strategy Planner (LLM)
- Step 7: Solutions Generator (LLM)
- Step 7.1: Visual Insights Analyzer (vision)
- Step 7.2: Creative Generation Layer (images + video storyboard)
- Step 8: Budget Estimator (rules)
- Step 9: Critic/Validator (quality gates)

### Step 4: Set Up n8n (1 hour)
- Start with self-hosted n8n locally (Docker) for fully free mode
- Optional: create account at cloud.n8n.io (free tier) if local hosting is not possible
- Create 3 core workflows first, then 2 multimodal workflows if time allows
- Get webhook URLs
- Add to FastAPI config

### Step 5: Test End-to-End (2 hours)
Following Step 22-25 in roadmap:
- Generate test campaign
- Verify solutions JSON is valid
- Verify text + image chat path returns visual insights
- Verify generated image/video storyboard metadata is persisted
- Check PostgreSQL tables in container
- Trigger n8n workflows manually

---

## Key Technical Decisions Already Made

✅ **FastAPI, not n8n, for generation**
- Reason: 2-6 second latency needed, n8n adds overhead

✅ **n8n only for background automation**
- Reason: Enrichment and learning don't need to be instant

✅ **Local-first inference with optional free-tier LLMs**
- Reason: 100% free baseline without subscriptions; Groq/Gemini free tiers can be enabled when quota is available

✅ **Structured creative brief endpoint as media fallback**
- Reason: reliable demo output even when image APIs are unavailable or quota-limited

✅ **Streaming generate endpoint for demo UX**
- Reason: shows progressive AI reasoning instead of long silent wait

✅ **Local PostgreSQL (Docker) as DB**
- Reason: no cloud dependency during hackathon, reproducible local setup

✅ **Self-hosted n8n as default automation runtime**
- Reason: fully free operations with no per-request billing

✅ **Solutions portfolio, not single caption**
- Reason: More valuable, more impressive to judges

✅ **Multimodal interaction (text + image)**
- Reason: stronger product realism and visual marketing intelligence

✅ **Evidence + confidence in every output**
- Reason: Builds trust, differentiator vs generic LLM

---

## File Locations

All docs in: `c:/Users/errac/Desktop/Side_missions/Hackaton_3/`

1. `PILLAR_3_IMPLEMENTATION_ROADMAP.md`
2. `PILLAR_3_DATABASE_SCHEMA.md`
3. `PILLAR_3_API_CONTRACTS.md`
4. `PILLAR_3_N8N_WORKFLOWS.md`
5. `hackathon_requirements_summary.md` (official brief)
6. `extracted_pypdf.txt` (raw PDF text)
7. `extracted_pdfplumber.txt` (raw PDF text)

---

## Team Roles (Recommended)

- **Dev 1 (Backend lead)**: Phases 1-4 (DB + FastAPI structure)
- **Dev 2 (AI/LLM)**: Phases 3-6 (generation logic + prompts)
- **Dev 3 (Automation)**: Phases 5, 9 (n8n workflows)
- **Dev 4 (QA + Demo)**: Phases 7-11 (testing, demo prep)

---

## Demo Scenario (< 2 minutes)

1. **Show brief input**: "Promote pain au levain, Instagram-focused, 2-week campaign"
2. **Hit generate**: Results appear in ~4-5 seconds
3. **Show portfolio**: 7 solutions with budgets: WhatsApp (50 TND), Instagram (300 TND), Email (0 TND), etc.
4. **Show reasoning**: Click on solution → reveal "why this works" + market signals used
5. **Show n8n**: Quick cut to n8n UI showing enrichment workflow running
6. **Close**: "Our platform turns every PME owner into a strategic marketer with data + budget planning"

---

## Success Criteria

✅ Generate endpoint works and returns valid JSON  
✅ Solutions include at least 5 different channels  
✅ Each solution has budget breakdown + reasoning  
✅ Confidence score reflects evidence actually used  
✅ Refine endpoint works (user can edit)  
✅ n8n Enricher workflow runs and populates DB  
✅ Demo runs live without timeouts  
✅ Judges understand: "This is a real marketing platform, not just AI prompting"  

---

## Questions? Edge Cases?

Before starting, clarify with your team:

1. **Language**: French, Arabic, or bilingual output? (Decision: auto-detect from location/audience)
2. **Sectors**: Any specific sectors to prioritize? (Start with food, e-commerce, services — general enough)
3. **Budget**: Min/max platform support? (Assume 0-5000 TND range)
4. **Integration**: Do we merge Pillar 3 with Pillar 1 or Pillar 2? (Recommend Pillar 2: Sales agent + Marketing agent = unified AI assistant)

---

## Good Luck! 🚀

You have everything you need to win this hackathon. Focus on:
1. **Depth over features** — 2 solutions done perfectly beats 7 done halfway
2. **Clear demos** — judges evaluate live, not code quality
3. **Business storytelling** — "how SMEs will actually benefit" > technical jargon
4. **Originality** — portfolio + budget = different from generic LLM
