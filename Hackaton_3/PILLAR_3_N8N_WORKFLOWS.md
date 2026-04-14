# Pillar 3: n8n Workflow Specifications

## Overview
3 core workflows + 2 multimodal workflows to automate enrichment, media generation, and feedback loops.

## Cost Model (Free-First)

1. Default: self-host n8n locally with Docker (no paid subscription).
2. Default workflow execution must not depend on paid APIs.
3. Optional API calls are allowed only via free-tier quotas.
4. If any quota is exhausted, workflow must degrade gracefully and keep core pipeline running.

---

## Workflow 1: Market Signal Enricher

**Trigger**: Cron job every 3 hours  
**Purpose**: Fetch fresh market data and populate `market_signals` table  
**Estimated runtime**: 2-3 minutes  
**Error handling**: Log failures, continue (don't block)

### Node-by-Node Blueprint

```
START (Cron: every 3 hours)
  ↓
[1] Cron Trigger
  - Schedule: 0 */3 * * * (every 3 hours)
  - Output: { "timestamp": NOW() }
  ↓
[2] HTTP GET - Google Trends (alternative sources)
  - URL: https://trends.google.com/api/explore (or RSS feed)
  OR scrape via free tools (pytrends)
  - Output: { "trends": ["pain artisanal", "sourdough", "bread health"] }
  - Error handling: skip if fails
  ↓
[3] HTTP GET - Local Events (Tunisia calendar)
  - URL: [local events API or scraped data]
  - Output: { "events": ["Ramadan_2026_start_March_30", "Eid_celebrations"] }
  ↓
[4] HTTP GET - Weather/Season Data
  - URL: [Open-Meteo free endpoint or hardcoded seasonal data]
  - Output: { "season": "spring", "temp_trend": "warming" }
  ↓
[5] Function Node - Normalize + Combine
  - Input: results from nodes 2, 3, 4
  - Logic:
    ```javascript
    const signals = [];
    
    // Add trends
    items[0].trends.forEach(trend => {
      signals.push({
        region: 'mena',
        source: 'google_trends',
        signal_type: 'trend',
        signal_key: trend.toLowerCase(),
        signal_value: trend,
        confidence: 0.85,
        fetched_at: new Date(),
        expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000) // 3 days
      });
    });
    
    // Add events
    items[1].events.forEach(event => {
      signals.push({
        region: 'tunisia',
        source: 'local_events',
        signal_type: 'event',
        signal_key: event,
        signal_value: event,
        confidence: 1.0,
        fetched_at: new Date(),
        expires_at: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000) // 60 days
      });
    });
    
    // Add season
    signals.push({
      region: 'mena',
      source: 'season_data',
      signal_type: 'season',
      signal_key: items[2].season,
      signal_value: items[2].season + ' - ' + items[2].temp_trend,
      confidence: 0.9,
      fetched_at: new Date()
    });
    
    return signals;
    ```
  - Output: array of normalized signal objects
  ↓
[6] Optional LLM Node - Signal Summarization (free-tier only: Groq/Gemini or local model)
  - Prompt: "Summarize which of these signals are most relevant for food/artisan businesses right now"
  - Input: normalized signals
  - Output: brief "top_signals" summary
  ↓
[7] PostgreSQL Upsert Batch
  - Table: `market_signals`
  - Mode: Upsert (on duplicate signal_key + region, update fetched_at)
  - Input: array from node 5 (or 6 if using LLM)
  - Batch size: 100
  ↓
[8] Slack Notification (optional)
  - Message: "Enriched {{outputs[7].insertedCount}} signals at {{now()}}"
  ↓
END
```

### Key Configuration Notes

1. **Cron Schedule**: `0 */3 * * *` = every 3 hours, 0 minutes
2. **Timeout per node**: 30s (n8n default safety)
3. **Error strategy**: 
   - If trends fetch fails: skip it, continue with events
   - If all sources fail: log and alert, don't upsert empty data
4. **PostgreSQL connection**:
  - Use PostgreSQL connector node in n8n
  - Connection string: `${POSTGRES_HOST}:${POSTGRES_PORT}` with `${POSTGRES_USER}` and `${POSTGRES_PASSWORD}`
   - Test connection before deploying

---

## Workflow 2: Campaign Ops Pipeline

**Trigger**: Webhook from FastAPI when campaign generated  
**Purpose**: Quality check + optional publish + log status  
**Estimated runtime**: 1-2 minutes  
**Use case**: Turn generated solutions into action

### Node-by-Node Blueprint

```
START (Webhook from backend)
  ↓
[1] Webhook Receiver
  - URL: https://your-n8n-instance.com/webhook/campaigns
  - Method: POST
  - Auth: Bearer token (set in FastAPI)
  - Input body expected:
    {
      "campaign_id": "...",
      "workspace_id": "...",
      "solutions": [...],
      "strategy": {...}
    }
  ↓
[2] PostgreSQL Read - Get workspace settings
  - Table: `brand_memory`
  - Filter: workspace_id = {{$node["Webhook Receiver"].json.workspace_id}}
  - Output: { "banned_phrases": [...], "max_budget": 1000 }
  ↓
[3] Function Node - Brand Safety Check
  - Input: solutions from webhook + banned_phrases from PostgreSQL
  - Logic:
    ```javascript
    const solutions = $node["Webhook Receiver"].json.solutions;
    const bannedPhrases = $node["PostgreSQL Read"].json[0].banned_phrases || [];
    
    const flagged = [];
    solutions.forEach(sol => {
      bannedPhrases.forEach(banned => {
        if (sol.reasoning.toLowerCase().includes(banned.toLowerCase())) {
          flagged.push({
            solution_id: sol.id,
            issue: `Contains banned phrase: "${banned}"`,
            severity: 'high'
          });
        }
      });
    });
    
    return {
      all_pass: flagged.length === 0,
      flagged_issues: flagged
    };
    ```
  - Output: { "all_pass": boolean, "flagged_issues": array }
  ↓
[4] IF Node - Decision: Safety check passed?
  - Condition: {{$node["Function Node"].json.all_pass}} === true
  - True path → continue to [5]
  - False path → [9] (alert + reject)
  ↓
(TRUE PATH)
[5] Function Node - Budget Verify
  - Check if any solution exceeds workspace max budget
  - Output: { "budget_ok": true/false }
  ↓
[6] PostgreSQL Update - Mark campaign as approved
  - Table: `campaigns`
  - Update: `status='approved'` where `id=campaign_id`
  ↓
[7] HTTP POST - Optional: Notify external service
  - If you have a publishing queue, notify it
  - Example: POST to job queue
  - OR skip if managing publishing separately
  ↓
[8] Slack/Email Notification (SUCCESS)
  - Message: "Campaign {{campaign_id}} passed all checks and is approved for action"
  ↓
(FALSE PATH)
[9] Slack/Email Notification (FAILURE)
  - Message: "Campaign {{campaign_id}} failed checks. Issues: {{flagged_issues}}"
  ↓
END
```

### Configuration

1. **Webhook URL**: You'll generate this from n8n UI after creating workflow
2. **Pass webhook URL to FastAPI**: Store in config, post to n8n on generation
3. **Retry logic**: n8n auto-retries 3x on network failure
4. **Timeout**: 30s total for workflow

### FastAPI integration code (pseudo-code)

```python
# In marketing_service.py
import requests

async def emit_campaign_generated_event(campaign_id: str, solutions: list):
    payload = {
        "campaign_id": campaign_id,
        "solutions": solutions,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            url=settings.N8N_WEBHOOK_URL,  # e.g., https://n8n.example.com/webhook/campaigns
            json=payload,
            headers={"Authorization": f"Bearer {settings.N8N_WEBHOOK_TOKEN}"},
            timeout=5
        )
        logger.info(f"Campaign event emitted to n8n: {response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to emit event: {e}")  # Don't block generation
```

---

## Workflow 3: Learning Loop

**Trigger**: Daily cron at midnight  
**Purpose**: Analyze yesterday's campaigns + update `brand_memory`  
**Estimated runtime**: 2-3 minutes  
**Impact**: Next generations become smarter

### Node-by-Node Blueprint

```
START (Cron: daily at midnight)
  ↓
[1] Cron Trigger
  - Schedule: 0 0 * * * (daily at 00:00)
  ↓
[2] PostgreSQL Query - Get yesterday's campaigns
  - Table: `campaign_feedback`
  - Filter: 
    - date(created_at) = yesterday
    - published = true
  - Fields: solution_id, channel, tone_recommendation, engagement_count, conversions
  ↓
[3] PostgreSQL Query - Get solution details
  - Table: `campaign_solutions`
  - Filter: id IN (solution_ids from [2])
  - Fields: channel, confidence_score, tone_recommendation
  ↓
[4] Function Node - Compute Winning Patterns
  - Input: feedback + solutions from [2] and [3]
  - Logic:
    ```javascript
    const feedback = $node["PostgreSQL Query - feedback"].json;
    const solutions = $node["PostgreSQL Query - solutions"].json;
    
    // Compute channel win rate
    const channelScores = {};
    feedback.forEach(fb => {
      const channel = solutions.find(s => s.id === fb.solution_id)?.channel;
      if (channel) {
        if (!channelScores[channel]) {
          channelScores[channel] = { wins: 0, total: 0, engagement_sum: 0 };
        }
        channelScores[channel].total++;
        channelScores[channel].engagement_sum += fb.engagement_count || 0;
        if (fb.conversions > 0) {
          channelScores[channel].wins++;
        }
      }
    });
    
    // Compute tone win rate
    const toneScores = {};
    feedback.forEach(fb => {
      const tone = solutions.find(s => s.id === fb.solution_id)?.tone_recommendation;
      if (tone) {
        if (!toneScores[tone]) {
          toneScores[tone] = { wins: 0, total: 0 };
        }
        toneScores[tone].total++;
        if (fb.conversions > 0) {
          toneScores[tone].wins++;
        }
      }
    });
    
    return {
      channel_scores: channelScores,
      tone_scores: toneScores,
      timestamp: new Date()
    };
    ```
  - Output: scored patterns object
  ↓
[5] Optional LLM Node - Generate insights
  - Prompt: "Based on yesterday's campaign performance, what should we emphasize more? Format as JSON."
  - Input: channel_scores and tone_scores
  - Output: insights
  - Note: run only when free-tier quota is available; otherwise skip node
  ↓
[6] PostgreSQL Update - Write to brand_memory
  - Table: `brand_memory`
  - Filter: workspace_id = {{workspace_id}} (if stateless, query from config or add as trigger param)
  - Update fields:
    ```javascript
    {
      "winning_tones_json": $node["Function Node"].json.tone_scores,
      "winning_channels_json": $node["Function Node"].json.channel_scores,
      "updated_at": new Date()
    }
    ```
  ↓
[7] Log Success
  - Slack: "Learning loop completed. Updated patterns for {{workspace_count}} workspaces."
  ↓
END
```

### Configuration

1. **Cron schedule**: Midnight UTC or local timezone
2. **Workspace iteration**: If multi-tenant, you may need to loop over all workspaces
3. **Stateless note**: Workflows are typically stateless, so pass workspace_id as parameter or hardcode for MVP

---

## Workflow 4: Creative Media Pipeline

**Trigger**: Webhook after media generation request  
**Purpose**: Generate/store image assets and optional video render jobs  
**Estimated runtime**: 1-4 minutes for image, variable for video render

### Node-by-Node Blueprint

```
START (Webhook from /media/generate-image or /media/generate-video-plan)
  ↓
[1] Webhook Receiver
  - Input body expected:
    {
      "workspace_id": "...",
      "campaign_id": "...",
      "task_type": "image_generation|video_storyboard|video_render",
      "prompt": "...",
      "constraints": {...}
    }
  ↓
[2] PostgreSQL Read - Load campaign context
  - Tables: `campaigns`, `campaign_strategies`, `brand_memory`
  - Output: style constraints + campaign objective
  ↓
[3] IF Node - task_type switch
  - image_generation -> [4A]
  - video_storyboard -> [4B]
  - video_render -> [4C]
  ↓
[4A] HTTP Request - Image Generation Provider
  - Send prompt + style constraints (free-tier provider only)
  - Output: generated image URL(s)
  ↓
[4B] LLM Node - Storyboard Generation
  - Output: structured shot list + script
  ↓
[4C] HTTP Request - Video Render Provider (optional)
  - Queue render job (free-tier provider only)
  - Output: job_id / status URL
  ↓
[5] PostgreSQL Upsert - Persist generated media
  - Table: `generated_media`
  - Fields: campaign_id, media_type, media_url/job_id, status, prompt_used
  ↓
[6] PostgreSQL Upsert - Persist diagnostics
  - Table: `visual_insights` (if analysis produced)
  ↓
[7] Notification (optional)
  - Slack/Email: "Creative assets ready for campaign {{campaign_id}}"
  ↓
END
```

### Configuration Notes

1. Keep video render optional for hackathon reliability.
2. If provider fails, store failed status in `generated_media` and return fallback plan.
3. Do not block synchronous user endpoint on long-running render jobs.

---

## Workflow 5: Media Publish Scheduler

**Trigger**: Cron or manual trigger  
**Purpose**: Push approved generated creatives to publication pipeline and collect delivery status  
**Estimated runtime**: 1-2 minutes

### Node-by-Node Blueprint

```
START (Cron every hour)
  ↓
[1] PostgreSQL Query - Fetch approved generated assets
  - Table: `generated_media`
  - Filter: status = 'approved' and publish_scheduled_at <= NOW()
  ↓
[2] IF Node - Channel routing
  - instagram/facebook/whatsapp/email
  ↓
[3] HTTP Request - Channel adapter
  - Send media_url + caption + metadata
  ↓
[4] PostgreSQL Update - Publish status
  - status = 'published' or 'failed'
  - store response payload / error
  ↓
[5] Optional analytics pull (delayed)
  - queue metric collection task for Workflow 3 learning input
  ↓
END
```

---

## Deployment Checklist

### Before activating any workflow

- [ ] n8n instance running (self-hosted recommended; cloud.n8n.io free tier optional)
- [ ] PostgreSQL connection configured in n8n credentials
- [ ] PostgreSQL tables exist (market_signals, campaign_feedback, brand_memory)
- [ ] Test PostgreSQL connector by doing a test query
- [ ] Get webhook URLs from n8n UI after creating workflows
- [ ] Add webhook URLs to FastAPI config
- [ ] Test each workflow manually first (click execute in n8n UI)
- [ ] Set cron schedules
- [ ] Activate 3 core workflows (1,2,3)
- [ ] Activate 2 multimodal workflows (4,5) when media endpoints are enabled

### Environment Variables (in n8n)

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=55432
POSTGRES_DB=marketing_ai_dev
POSTGRES_USER=marketing_user
POSTGRES_PASSWORD=marketing_pwd_local

# Optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
LLM_API_KEY=groq_xxxx  # optional, free-tier only
GEMINI_API_KEY=AIza... # optional, free-tier only
```

---

## Testing Each Workflow

### Workflow 1 (Enricher)

1. Click "Execute Workflow" in n8n UI
2. Check PostgreSQL table: should see new rows in `market_signals`
3. Verify `expires_at` is set correctly (3-60 days from now)

### Workflow 2 (Ops Pipeline)

1. Manually trigger webhook with curl:
   ```bash
   curl -X POST https://your-n8n/webhook/campaigns \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "campaign_id": "test_123",
       "solutions": [{"id": "s1", "channel": "email", "reasoning": "safe"}]
     }'
   ```
2. Should receive Slack notification of approval

### Workflow 3 (Learning)

1. Ensure `campaign_feedback` has rows with `created_at` yesterday
2. Click "Execute Workflow"
3. Check PostgreSQL `brand_memory` table: should see updated `winning_tones_json`

### Workflow 4 (Creative Media Pipeline)

1. Trigger webhook with an image generation payload.
2. Confirm generated asset metadata is written to `generated_media`.
3. Confirm status transitions (`queued` -> `ready` or `failed`) are logged.

### Workflow 5 (Media Publish Scheduler)

1. Insert an approved `generated_media` row with publish schedule in the past.
2. Run workflow and verify publish adapter is called.
3. Confirm row is updated to `published` or `failed`.

---

## Troubleshooting

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| Workflow times out | Node is hanging (HTTP request slow) | Add timeout to HTTP nodes (30s max) |
| PostgreSQL upsert failing | Wrong table name, SQL query, or missing columns | Verify table exists and SQL is valid |
| Webhook never fires | n8n webhook not called from FastAPI | Check FastAPI is actually making request, verify URL, check logs |
| Learning loop shows no data | No campaigns yesterday | Create test campaigns first |

---

## Optional Enhancements (Post-MVP)

1. **Add Workflow 6**: Post-publication metrics collector (pull analytics after 24h)
2. **Add Workflow 7**: Daily performance report generator (email/WhatsApp digest)
3. **Add error recovery**: DLQ workflow for failed media generation/publishing jobs
