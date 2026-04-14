CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) NOT NULL,
  sector VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  region VARCHAR(50) NOT NULL,
  source VARCHAR(100) NOT NULL,
  signal_type VARCHAR(50) NOT NULL,
  signal_key VARCHAR(255) NOT NULL,
  signal_value TEXT NOT NULL,
  confidence DECIMAL(3,2) NOT NULL DEFAULT 0.80,
  tags JSONB NOT NULL DEFAULT '{}'::jsonb,
  fetched_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT signal_validity CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT future_expiry CHECK (expires_at IS NULL OR expires_at > fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_market_signals_region_type ON market_signals(region, signal_type);
CREATE INDEX IF NOT EXISTS idx_market_signals_expires_at ON market_signals(expires_at);
CREATE INDEX IF NOT EXISTS idx_market_signals_workspace ON market_signals(workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_market_signals_workspace_region_key
ON market_signals(workspace_id, region, signal_key);

CREATE TABLE IF NOT EXISTS marketing_solutions_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(50) NOT NULL,
  solution_name VARCHAR(255) NOT NULL,
  description TEXT,
  budget_low DECIMAL(10,2),
  budget_high DECIMAL(10,2),
  effort_level VARCHAR(20),
  sectors JSONB NOT NULL DEFAULT '[]'::jsonb,
  typical_assets JSONB NOT NULL DEFAULT '{}'::jsonb,
  timeline_weeks INT,
  frequency_recommendation VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT budget_range_valid CHECK (budget_low IS NULL OR budget_high IS NULL OR budget_low <= budget_high)
);

CREATE INDEX IF NOT EXISTS idx_solutions_library_channel ON marketing_solutions_library(channel);
CREATE UNIQUE INDEX IF NOT EXISTS uq_solutions_library_channel_name
ON marketing_solutions_library(channel, solution_name);

CREATE TABLE IF NOT EXISTS campaign_briefs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  created_by VARCHAR(255),
  product_name VARCHAR(255) NOT NULL,
  product_description TEXT,
  product_category VARCHAR(100),
  audience_age_min INT,
  audience_age_max INT,
  audience_location VARCHAR(255),
  audience_interests JSONB NOT NULL DEFAULT '[]'::jsonb,
  audience_segment VARCHAR(100),
  objective VARCHAR(50) NOT NULL,
  campaign_timeline VARCHAR(100),
  budget_constraint_low DECIMAL(10,2),
  budget_constraint_high DECIMAL(10,2),
  language_preference VARCHAR(20) NOT NULL DEFAULT 'fr',
  tone_preference VARCHAR(50),
  banned_phrases JSONB NOT NULL DEFAULT '[]'::jsonb,
  constraints_text TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT age_range_valid CHECK (audience_age_min IS NULL OR audience_age_max IS NULL OR audience_age_min <= audience_age_max),
  CONSTRAINT brief_budget_valid CHECK (budget_constraint_low IS NULL OR budget_constraint_high IS NULL OR budget_constraint_low <= budget_constraint_high),
  CONSTRAINT objective_valid CHECK (objective IN ('awareness', 'engagement', 'leads', 'sales'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_briefs_workspace ON campaign_briefs(workspace_id);

CREATE TABLE IF NOT EXISTS campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  brief_id UUID NOT NULL REFERENCES campaign_briefs(id) ON DELETE CASCADE,
  status VARCHAR(30) NOT NULL DEFAULT 'generated',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT campaign_status_valid CHECK (status IN ('generated', 'approved', 'rejected', 'scheduled', 'published', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_campaigns_workspace ON campaigns(workspace_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);

CREATE TABLE IF NOT EXISTS campaign_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  positioning TEXT,
  target_psychology TEXT,
  market_opportunity TEXT,
  messaging_pillars JSONB NOT NULL DEFAULT '[]'::jsonb,
  tone_recommendation VARCHAR(50),
  channel_priorities JSONB NOT NULL DEFAULT '[]'::jsonb,
  timeline_summary VARCHAR(255),
  risk_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
  model_used VARCHAR(100),
  latency_ms INT,
  confidence_strategy DECIMAL(3,2),
  tokens_used INT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT strategy_confidence_valid CHECK (confidence_strategy IS NULL OR (confidence_strategy >= 0 AND confidence_strategy <= 1))
);

CREATE INDEX IF NOT EXISTS idx_campaign_strategies_campaign ON campaign_strategies(campaign_id);

CREATE TABLE IF NOT EXISTS campaign_solutions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  strategy_id UUID REFERENCES campaign_strategies(id) ON DELETE SET NULL,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  solution_index INT,
  channel VARCHAR(50) NOT NULL,
  solution_name VARCHAR(255),
  description TEXT,
  execution JSONB NOT NULL DEFAULT '{}'::jsonb,
  budget JSONB NOT NULL DEFAULT '{}'::jsonb,
  expected_outcomes JSONB NOT NULL DEFAULT '{}'::jsonb,
  confidence_score DECIMAL(3,2),
  reasoning TEXT,
  signals_used JSONB NOT NULL DEFAULT '[]'::jsonb,
  risk_level VARCHAR(20),
  model_used VARCHAR(100),
  latency_ms INT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT solution_confidence_valid CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
  CONSTRAINT risk_level_valid CHECK (risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'low_but_slow'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_solutions_campaign ON campaign_solutions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_solutions_workspace ON campaign_solutions(workspace_id);

CREATE TABLE IF NOT EXISTS campaign_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  solution_id UUID NOT NULL REFERENCES campaign_solutions(id) ON DELETE CASCADE,
  selected BOOLEAN NOT NULL DEFAULT FALSE,
  edited_content TEXT,
  published BOOLEAN NOT NULL DEFAULT FALSE,
  published_at TIMESTAMP,
  published_url VARCHAR(500),
  impressions INT,
  clicks INT,
  conversions INT,
  engagement_count INT,
  collected_at TIMESTAMP,
  user_notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT metrics_non_negative CHECK (
    (impressions IS NULL OR impressions >= 0) AND
    (clicks IS NULL OR clicks >= 0) AND
    (conversions IS NULL OR conversions >= 0) AND
    (engagement_count IS NULL OR engagement_count >= 0)
  )
);

CREATE INDEX IF NOT EXISTS idx_campaign_feedback_workspace ON campaign_feedback(workspace_id);
CREATE INDEX IF NOT EXISTS idx_campaign_feedback_campaign ON campaign_feedback(campaign_id);

CREATE TABLE IF NOT EXISTS brand_memory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
  preferred_tone VARCHAR(50),
  language_preference VARCHAR(20),
  banned_phrases JSONB NOT NULL DEFAULT '[]'::jsonb,
  winning_tones_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  winning_channels_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  winning_budget_range JSONB NOT NULL DEFAULT '{}'::jsonb,
  max_budget_preference DECIMAL(10,2),
  sector_category VARCHAR(100),
  target_location VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brand_memory_workspace ON brand_memory(workspace_id);

CREATE TABLE IF NOT EXISTS campaign_generation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  brief_id UUID REFERENCES campaign_briefs(id) ON DELETE SET NULL,
  request_hash VARCHAR(255),
  prompt_version VARCHAR(50),
  solutions_count INT,
  total_latency_ms INT,
  tokens_input INT,
  tokens_output INT,
  cost_estimate DECIMAL(10,4),
  passed_critic BOOLEAN,
  critic_notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generation_logs_workspace ON campaign_generation_logs(workspace_id);

DROP TRIGGER IF EXISTS trg_workspaces_updated_at ON workspaces;
CREATE TRIGGER trg_workspaces_updated_at
BEFORE UPDATE ON workspaces
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_market_signals_updated_at ON market_signals;
CREATE TRIGGER trg_market_signals_updated_at
BEFORE UPDATE ON market_signals
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_solutions_library_updated_at ON marketing_solutions_library;
CREATE TRIGGER trg_solutions_library_updated_at
BEFORE UPDATE ON marketing_solutions_library
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_campaign_briefs_updated_at ON campaign_briefs;
CREATE TRIGGER trg_campaign_briefs_updated_at
BEFORE UPDATE ON campaign_briefs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_campaigns_updated_at ON campaigns;
CREATE TRIGGER trg_campaigns_updated_at
BEFORE UPDATE ON campaigns
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_campaign_feedback_updated_at ON campaign_feedback;
CREATE TRIGGER trg_campaign_feedback_updated_at
BEFORE UPDATE ON campaign_feedback
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_brand_memory_updated_at ON brand_memory;
CREATE TRIGGER trg_brand_memory_updated_at
BEFORE UPDATE ON brand_memory
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
