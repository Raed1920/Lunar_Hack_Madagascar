INSERT INTO workspaces (id, name, sector)
VALUES ('11111111-1111-1111-1111-111111111111', 'Marketing AI Demo Workspace', 'food_artisan')
ON CONFLICT (id) DO NOTHING;

INSERT INTO brand_memory (
  workspace_id,
  preferred_tone,
  language_preference,
  banned_phrases,
  max_budget_preference,
  sector_category,
  target_location
)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'storytelling',
  'bilingual',
  '["guaranteed profit", "miracle", "100% instant results"]'::jsonb,
  1500,
  'food_artisan',
  'Tunis'
)
ON CONFLICT (workspace_id) DO NOTHING;

INSERT INTO marketing_solutions_library (
  channel,
  solution_name,
  description,
  budget_low,
  budget_high,
  effort_level,
  sectors,
  typical_assets,
  timeline_weeks,
  frequency_recommendation
)
VALUES
(
  'social_media',
  'Instagram Storytelling Campaign',
  'Reels and stories focused on behind-the-scenes artisan process and customer moments.',
  80,
  350,
  'medium',
  '["food", "artisan", "ecommerce"]'::jsonb,
  '{"formats": ["reels", "stories"], "needs": ["phone_camera", "simple_editor"]}'::jsonb,
  2,
  '3x per week'
),
(
  'whatsapp',
  'WhatsApp Broadcast Offers',
  'Daily or weekly broadcast messages with stock availability and promotions.',
  0,
  120,
  'low',
  '["food", "retail", "services"]'::jsonb,
  '{"formats": ["broadcast"], "needs": ["whatsapp_business"]}'::jsonb,
  1,
  'daily'
),
(
  'email',
  'Email Retention Sequence',
  'Weekly newsletter plus targeted promotional messages for repeat customers.',
  0,
  200,
  'low',
  '["ecommerce", "food", "services"]'::jsonb,
  '{"formats": ["newsletter"], "needs": ["email_tool", "template"]}'::jsonb,
  2,
  'weekly'
),
(
  'events',
  'Local Pop-up Event Activation',
  'Small local event presence with sampling and direct customer acquisition.',
  400,
  1500,
  'high',
  '["food", "artisan", "retail"]'::jsonb,
  '{"formats": ["booth"], "needs": ["stand", "staff", "sampling"]}'::jsonb,
  3,
  'seasonal'
)
ON CONFLICT DO NOTHING;

INSERT INTO market_signals (
  workspace_id,
  region,
  source,
  signal_type,
  signal_key,
  signal_value,
  confidence,
  tags,
  expires_at
)
VALUES
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'season_data',
  'event',
  'ramadan_2026',
  'Ramadan period drives higher evening and pre-iftar food demand.',
  1.00,
  '{"category": "food", "urgency": "high"}'::jsonb,
  NOW() + INTERVAL '45 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'mena',
  'social_trend',
  'trend',
  'short_video_priority',
  'Short-form videos are getting higher organic reach than static visuals.',
  0.90,
  '{"category": "social_media", "channel": "instagram"}'::jsonb,
  NOW() + INTERVAL '7 days'

),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'retail_calendar',
  'event',
  'eid_shopping_peak',
  'Demand spikes in the 7-10 days before Eid for family food and gifts.',
  0.95,
  '{"category": "seasonality", "window": "pre_eid"}'::jsonb,
  NOW() + INTERVAL '30 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'education_calendar',
  'event',
  'back_to_school_cycle',
  'Back-to-school period increases household planning and convenience purchases.',
  0.86,
  '{"category": "seasonality", "window": "school"}'::jsonb,
  NOW() + INTERVAL '60 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'weather_pattern',
  'season',
  'summer_heat_effect',
  'High temperatures shift customer activity to early morning and late evening.',
  0.84,
  '{"category": "timing", "season": "summer"}'::jsonb,
  NOW() + INTERVAL '75 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'consumer_behavior',
  'trend',
  'weekend_family_buying',
  'Weekend family gatherings increase demand for larger food orders.',
  0.82,
  '{"category": "food", "day": "weekend"}'::jsonb,
  NOW() + INTERVAL '21 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'messaging_trend',
  'trend',
  'whatsapp_ordering_preference',
  'Customers prefer quick ordering and confirmation through WhatsApp.',
  0.91,
  '{"category": "channel", "channel": "whatsapp"}'::jsonb,
  NOW() + INTERVAL '30 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'mena',
  'platform_trend',
  'trend',
  'instagram_reels_discovery_2026',
  'Instagram Reels gets stronger discovery than static feed posts for local brands.',
  0.88,
  '{"category": "channel", "channel": "instagram"}'::jsonb,
  NOW() + INTERVAL '14 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'mena',
  'platform_trend',
  'trend',
  'tiktok_local_reach_growth',
  'TikTok local discovery continues to grow for food and lifestyle niches.',
  0.83,
  '{"category": "channel", "channel": "tiktok"}'::jsonb,
  NOW() + INTERVAL '14 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'email_behavior',
  'trend',
  'email_midweek_open_window',
  'Email opens are typically stronger on Tuesday and Wednesday late morning.',
  0.79,
  '{"category": "channel", "channel": "email"}'::jsonb,
  NOW() + INTERVAL '30 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'pricing_signal',
  'trend',
  'price_sensitivity_mid_market',
  'Mid-market buyers respond better to bundles than direct discounting.',
  0.80,
  '{"category": "pricing", "segment": "mid_market"}'::jsonb,
  NOW() + INTERVAL '40 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'local_events',
  'event',
  'weekend_market_footfall',
  'Neighborhood weekend markets drive high product sampling opportunities.',
  0.87,
  '{"category": "events", "format": "offline"}'::jsonb,
  NOW() + INTERVAL '20 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'search_trend',
  'trend',
  'artisan_food_search_uplift',
  'Search interest for artisan and natural food has a sustained uplift.',
  0.85,
  '{"category": "demand", "theme": "artisan"}'::jsonb,
  NOW() + INTERVAL '18 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'mena',
  'content_trend',
  'trend',
  'behind_the_scenes_trust',
  'Behind-the-scenes production content increases trust and repeat intent.',
  0.81,
  '{"category": "content", "format": "behind_the_scenes"}'::jsonb,
  NOW() + INTERVAL '25 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'mobility_pattern',
  'season',
  'commute_morning_purchase_window',
  'Morning commute window supports short urgency-based offers.',
  0.78,
  '{"category": "timing", "window": "morning"}'::jsonb,
  NOW() + INTERVAL '10 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'consumer_behavior',
  'trend',
  'subscription_box_interest',
  'Customers show growing interest in weekly subscription bundles.',
  0.77,
  '{"category": "retention", "model": "subscription"}'::jsonb,
  NOW() + INTERVAL '30 days'
),
(
  '11111111-1111-1111-1111-111111111111',
  'tunisia',
  'operations_signal',
  'trend',
  'same_day_delivery_expectation',
  'Same-day delivery expectation is rising in urban customer segments.',
  0.76,
  '{"category": "service", "segment": "urban"}'::jsonb,
  NOW() + INTERVAL '15 days'
)
ON CONFLICT DO NOTHING;
