ALTER TABLE market_signals
  ADD COLUMN IF NOT EXISTS meta_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE market_signals
  ALTER COLUMN workspace_id SET DEFAULT '11111111-1111-1111-1111-111111111111'::uuid;

CREATE UNIQUE INDEX IF NOT EXISTS uq_market_signals_region_key
ON market_signals(region, signal_key);

ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS strategy_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS review_notes_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE campaign_strategies
  ADD COLUMN IF NOT EXISTS constraints_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE campaign_strategies
  ADD COLUMN IF NOT EXISTS strategy_json JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE campaign_solutions
  ADD COLUMN IF NOT EXISTS tone_recommendation VARCHAR(50);

ALTER TABLE campaign_feedback
  ADD COLUMN IF NOT EXISTS channel VARCHAR(50);

ALTER TABLE campaign_feedback
  ADD COLUMN IF NOT EXISTS tone_recommendation VARCHAR(50);

ALTER TABLE brand_memory
  ADD COLUMN IF NOT EXISTS max_budget DECIMAL(10,2);

UPDATE brand_memory
SET max_budget = max_budget_preference
WHERE max_budget IS NULL AND max_budget_preference IS NOT NULL;

CREATE TABLE IF NOT EXISTS generated_media (
  id BIGSERIAL PRIMARY KEY,
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  media_type VARCHAR(30) NOT NULL,
  task_type VARCHAR(60) NOT NULL,
  channel VARCHAR(60),
  media_url TEXT,
  job_id VARCHAR(255),
  status VARCHAR(40) NOT NULL DEFAULT 'queued',
  prompt_used TEXT,
  provider_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  publish_response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT,
  publish_scheduled_at TIMESTAMP,
  published_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT generated_media_status_valid CHECK (
    status IN ('queued', 'ready', 'approved', 'published', 'failed')
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_generated_media_campaign_task
ON generated_media(campaign_id, task_type);

CREATE INDEX IF NOT EXISTS idx_generated_media_workspace_status
ON generated_media(workspace_id, status);

CREATE INDEX IF NOT EXISTS idx_generated_media_publish_schedule
ON generated_media(publish_scheduled_at);

CREATE TABLE IF NOT EXISTS visual_insights (
  id BIGSERIAL PRIMARY KEY,
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  insight_type VARCHAR(80) NOT NULL,
  insight_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visual_insights_campaign
ON visual_insights(campaign_id);

CREATE INDEX IF NOT EXISTS idx_visual_insights_workspace
ON visual_insights(workspace_id);

DROP TRIGGER IF EXISTS trg_generated_media_updated_at ON generated_media;
CREATE TRIGGER trg_generated_media_updated_at
BEFORE UPDATE ON generated_media
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_visual_insights_updated_at ON visual_insights;
CREATE TRIGGER trg_visual_insights_updated_at
BEFORE UPDATE ON visual_insights
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
