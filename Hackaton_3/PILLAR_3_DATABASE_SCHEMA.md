# Pillar 3: Exact Database Schemas (SQL/DDL)

Note: the canonical executable schema for local PostgreSQL is in `infra/postgres/init/010_schema.sql` and seed data is in `infra/postgres/init/020_seed.sql`. Use this document as reference and examples.

## 1. market_signals
Stores real-time trends, events, seasonality, and market intelligence.

```sql
CREATE TABLE market_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region VARCHAR(50) NOT NULL, -- 'tunisia', 'mena', 'global'
  source VARCHAR(100) NOT NULL, -- 'google_trends', 'local_events', 'weather', 'social_sentiment', 'custom'
  signal_type VARCHAR(50) NOT NULL, -- 'trend', 'event', 'season', 'competitor', 'cultural'
  signal_key VARCHAR(255) NOT NULL, -- 'ramadan_2026', 'summer_fashion', 'back_to_school'
  signal_value TEXT NOT NULL, -- human readable: "Ramadan starts March 30"
  confidence DECIMAL(3,2) DEFAULT 0.8, -- 0.0 to 1.0
  tags JSONB DEFAULT '{}'::jsonb, -- {"category": "food", "urgency": "high"}
  fetched_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP, -- when signal becomes stale
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  CONSTRAINT signal_validity CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT future_expiry CHECK (expires_at > fetched_at)
);

CREATE INDEX idx_market_signals_region_type ON market_signals(region, signal_type);
CREATE INDEX idx_market_signals_expires_at ON market_signals(expires_at);
```

---

## 2. marketing_solutions_library
Pre-built solution templates with budget ranges (populated manually or via seed script).

```sql
CREATE TABLE marketing_solutions_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(50) NOT NULL, -- 'social_media', 'email', 'sms', 'events', 'partnerships', 'paid_ads', 'content', 'influencer', 'pr', 'loyalty'
  solution_name VARCHAR(255) NOT NULL,
  description TEXT,
  
  -- Budget guidance (in TND)
  budget_low DECIMAL(10,2),
  budget_high DECIMAL(10,2),
  effort_level VARCHAR(20), -- 'low', 'medium', 'high'
  
  -- Applicable sectors
  sectors JSONB DEFAULT '{}'::jsonb, -- ["ecommerce", "food", "services", "artisan"]
  
  -- Template fields
  typical_assets JSONB DEFAULT '{}'::jsonb, -- what you need to create
  timeline_weeks INT,
  frequency_recommendation VARCHAR(100), -- "3x per week", "weekly"
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO marketing_solutions_library VALUES
  (
    gen_random_uuid(), 
    'social_media', 
    'Instagram Storytelling Campaign',
    'Use Instagram Reels and Stories to tell your brand story',
    100, 500,
    'medium',
    '["ecommerce", "artisan", "food"]'::jsonb,
    '{"content_format": "video", "tools": "instagram"}',
    2,
    '3x per week',
    NOW(),
    NOW()
  );
```

---

## 3. campaign_briefs
User input: the marketing request.

```sql
CREATE TABLE campaign_briefs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL, -- tenant isolation
  created_by VARCHAR(255),
  
  -- Business/Product info
  product_name VARCHAR(255) NOT NULL,
  product_description TEXT,
  product_category VARCHAR(100),
  
  -- Target audience
  audience_age_min INT,
  audience_age_max INT,
  audience_location VARCHAR(255), -- "Tunis", "Tunisia", "MENA"
  audience_interests JSONB DEFAULT '{}'::jsonb, -- ["fashion", "sustainability"]
  audience_segment VARCHAR(100), -- "premium", "budget", "mass_market"
  
  -- Campaign parameters
  objective VARCHAR(50) NOT NULL, -- 'awareness', 'engagement', 'leads', 'sales'
  campaign_timeline VARCHAR(100), -- "2 weeks urgent", "next month"
  budget_constraint_low DECIMAL(10,2),
  budget_constraint_high DECIMAL(10,2),
  
  -- Preferences
  language_preference VARCHAR(20) DEFAULT 'fr', -- 'fr', 'ar', 'bilingual'
  tone_preference VARCHAR(50), -- 'professional', 'fun', 'storytelling'
  banned_phrases JSONB DEFAULT '{}'::jsonb,
  constraints_text TEXT, -- free-form constraints
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_briefs_workspace ON campaign_briefs(workspace_id);
```

---

## 4. campaign_strategies
AI-generated strategy (output of Strategy Planner step).

```sql
CREATE TABLE campaign_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brief_id UUID NOT NULL REFERENCES campaign_briefs(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL,
  
  -- Strategy output (stored as JSON)
  positioning TEXT, -- why product matters now
  target_psychology TEXT, -- what audience fears/wants
  market_opportunity TEXT, -- seasonal/trend angle
  messaging_pillars JSONB DEFAULT '[]'::jsonb,
  tone_recommendation VARCHAR(50),
  channel_priorities JSONB DEFAULT '[]'::jsonb, -- ["instagram", "email", "events"]
  timeline_summary VARCHAR(255),
  risk_notes JSONB DEFAULT '[]'::jsonb,
  
  -- Metadata
  model_used VARCHAR(100), -- 'local_rules', 'local_ollama', 'groq_llama', 'gemini'
  latency_ms INT,
  confidence_strategy DECIMAL(3,2),
  tokens_used INT,
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_strategies_brief ON campaign_strategies(brief_id);
```

---

## 5. campaign_solutions
Generated solution portfolio (output of Solutions Generator step).

```sql
CREATE TABLE campaign_solutions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES campaign_strategies(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL,
  
  -- Solution individual fields
  solution_index INT, -- 0, 1, 2...
  channel VARCHAR(50) NOT NULL,
  solution_name VARCHAR(255),
  description TEXT,
  
  -- Execution details (JSON)
  execution JSONB,
  -- Example structure:
  -- {
  --   "content_format": "video|carousel|static|story|reel",
  --   "message": "core message",
  --   "assets_needed": ["script", "footage"],
  --   "timeline": "2 weeks to launch",
  --   "frequency": "3x per week"
  -- }
  
  -- Budget breakdown (JSON)
  budget JSONB,
  -- Example structure:
  -- {
  --   "total_low": 100,
  --   "total_high": 500,
  --   "currency": "TND",
  --   "breakdown": {
  --     "content_creation": 100,
  --     "ad_spend": 200,
  --     "management": 100,
  --     "tools": 50
  --   }
  -- }
  
  -- Expected outcomes (JSON)
  expected_outcomes JSONB,
  -- Example: {
  --   "reach": "10k-50k",
  --   "engagement_rate": "3-5%",
  --   "conversion_assumption": "1-2%",
  --   "roi_estimate": "3x-5x"
  -- }
  
  confidence_score DECIMAL(3,2),
  reasoning TEXT, -- why this works
  signals_used JSONB DEFAULT '[]'::jsonb, -- ["ramadan_trend", "event_1"]
  risk_level VARCHAR(20), -- 'low', 'medium', 'high'
  
  -- Metadata
  model_used VARCHAR(100), -- local or free-tier provider identifier
  latency_ms INT,
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_solutions_strategy ON campaign_solutions(strategy_id);
CREATE INDEX idx_campaign_solutions_workspace ON campaign_solutions(workspace_id);
```

---

## 6. campaign_feedback
User choice, edits, performance data (for learning loop).

```sql
CREATE TABLE campaign_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  solution_id UUID NOT NULL REFERENCES campaign_solutions(id) ON DELETE CASCADE,
  
  -- User choice
  selected BOOLEAN DEFAULT FALSE,
  edited_content TEXT, -- user's edits to the solution
  
  -- Execution
  published BOOLEAN DEFAULT FALSE,
  published_at TIMESTAMP,
  published_url VARCHAR(500),
  
  -- Performance (populated later by n8n or manual input)
  impressions INT,
  clicks INT,
  conversions INT,
  engagement_count INT,
  collected_at TIMESTAMP,
  
  -- Qualitative feedback
  user_notes TEXT,
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_feedback_workspace ON campaign_feedback(workspace_id);
```

---

## 7. brand_memory
Workspace preferences and learned patterns (updated by n8n Learning Loop).

```sql
CREATE TABLE brand_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL UNIQUE,
  
  -- Preferences (set by user)
  preferred_tone VARCHAR(50), -- 'professional', 'fun', 'storytelling'
  language_preference VARCHAR(20),
  banned_phrases JSONB DEFAULT '[]'::jsonb,
  
  -- Winning patterns (learned by n8n)
  winning_tones_json JSONB DEFAULT '{}'::jsonb,
  -- Example: {
  --   "instagram": {"professional": 0.3, "fun": 0.7},
  --   "email": {"professional": 0.8}
  -- }
  
  winning_channels_json JSONB DEFAULT '{}'::jsonb,
  -- Example: {"instagram": 0.85, "email": 0.6}
  
  winning_budget_range JSONB DEFAULT '{}'::jsonb,
  -- Example: {"best_roi": [200, 500], "best_speed": [0, 100]}
  
  -- Constraints learned
  max_budget_preference DECIMAL(10,2),
  sector_category VARCHAR(100),
  target_location VARCHAR(255),
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_brand_memory_workspace ON brand_memory(workspace_id);
```

---

## 8. campaign_generation_logs (optional, for debugging)
Track all generation requests for audit and improvement.

```sql
CREATE TABLE campaign_generation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  brief_id UUID REFERENCES campaign_briefs(id),
  
  -- Request metadata
  request_hash VARCHAR(255), -- to detect duplicates
  prompt_version VARCHAR(50),
  
  -- Response metadata
  solutions_count INT,
  total_latency_ms INT,
  tokens_input INT,
  tokens_output INT,
  cost_estimate DECIMAL(10,4),
  
  -- Quality
  passed_critic BOOLEAN,
  critic_notes TEXT,
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generation_logs_workspace ON campaign_generation_logs(workspace_id);
```

---

## 9. chat_sessions
Stores assistant conversation context per workspace/user.

```sql
CREATE TABLE chat_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  user_id VARCHAR(255),
  title VARCHAR(255),
  status VARCHAR(30) DEFAULT 'active', -- active, archived
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_sessions_workspace ON chat_sessions(workspace_id);
```

---

## 10. chat_messages
Stores chat messages, including multimodal attachments.

```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL,
  role VARCHAR(20) NOT NULL, -- user, assistant, system
  message_text TEXT,
  attached_asset_ids JSONB DEFAULT '[]'::jsonb,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_workspace ON chat_messages(workspace_id);
```

---

## 11. media_assets
Tracks uploaded media used as input to the assistant.

```sql
CREATE TABLE media_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  campaign_id UUID,
  uploaded_by VARCHAR(255),
  asset_type VARCHAR(20) NOT NULL, -- image, video
  storage_url TEXT NOT NULL,
  mime_type VARCHAR(100),
  file_size_bytes BIGINT,
  width INT,
  height INT,
  duration_seconds INT,
  checksum VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_media_assets_workspace ON media_assets(workspace_id);
CREATE INDEX idx_media_assets_campaign ON media_assets(campaign_id);
```

---

## 12. visual_insights
Stores structured insights extracted from uploaded or generated creatives.

```sql
CREATE TABLE visual_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  campaign_id UUID,
  asset_id UUID REFERENCES media_assets(id) ON DELETE SET NULL,
  insight_type VARCHAR(50) NOT NULL, -- composition, branding, cta_readability, quality
  score DECIMAL(4,3),
  findings JSONB DEFAULT '{}'::jsonb,
  recommendations JSONB DEFAULT '[]'::jsonb,
  model_used VARCHAR(100), -- local vision model or optional free-tier provider
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_visual_insights_workspace ON visual_insights(workspace_id);
CREATE INDEX idx_visual_insights_campaign ON visual_insights(campaign_id);
```

---

## 13. generated_media
Stores generated image variants and optional video plan/render outputs.

```sql
CREATE TABLE generated_media (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  campaign_id UUID,
  media_type VARCHAR(30) NOT NULL, -- image, video_storyboard, video_render
  prompt_used TEXT,
  provider VARCHAR(100), -- local engine or optional free-tier service
  output_url TEXT,
  output_payload JSONB DEFAULT '{}'::jsonb,
  status VARCHAR(30) DEFAULT 'ready', -- queued, processing, ready, failed, published
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generated_media_workspace ON generated_media(workspace_id);
CREATE INDEX idx_generated_media_campaign ON generated_media(campaign_id);
CREATE INDEX idx_generated_media_status ON generated_media(status);
```

---

## Key Design Principles

1. **Tenant isolation**: Every table has `workspace_id` for multi-tenant support.
2. **JSON for flexibility**: Execution, budget, outcomes stored as JSONB for schema evolution.
3. **Immutability**: `campaign_briefs` and `campaign_solutions` are write-once (used for learning).
4. **Efficiency**: Indexes on common filters (workspace, created_at, expires_at).
5. **Auditability**: creation/update timestamps on everything.
6. **Multimodal traceability**: Keep every uploaded and generated asset linked to campaign and workspace.
7. **Asynchronous safety**: Track media generation lifecycle (`queued` -> `ready`/`failed`) for workflow resilience.

---

## Setup Steps

```powershell
# Start local PostgreSQL (Docker)
./scripts/db_up.ps1

# Check status/logs
./scripts/db_status.ps1

# Connect to psql inside container
docker compose exec postgres psql -U marketing_user -d marketing_ai_dev

# Stop stack when needed
./scripts/db_down.ps1
```
