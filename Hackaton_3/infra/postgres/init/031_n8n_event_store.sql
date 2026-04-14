CREATE TABLE IF NOT EXISTS n8n_event_store (
  id BIGSERIAL PRIMARY KEY,
  workflow_key VARCHAR(80) NOT NULL,
  endpoint_url TEXT NOT NULL,
  request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  response_payload_json JSONB,
  status_code INT,
  latency_ms INT,
  success BOOLEAN NOT NULL DEFAULT FALSE,
  error_message TEXT,
  workspace_id_text VARCHAR(64),
  campaign_id_text VARCHAR(64),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_workflow
ON n8n_event_store(workflow_key);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_created_at
ON n8n_event_store(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_workspace
ON n8n_event_store(workspace_id_text);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_campaign
ON n8n_event_store(campaign_id_text);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_success
ON n8n_event_store(success);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_request_gin
ON n8n_event_store USING GIN (request_payload_json);

CREATE INDEX IF NOT EXISTS idx_n8n_event_store_response_gin
ON n8n_event_store USING GIN (response_payload_json);
