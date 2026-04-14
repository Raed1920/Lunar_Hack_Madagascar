# Pillar 3: Exact FastAPI Endpoint Contracts

## Base URL
```
http://localhost:8000/v1/marketing
```

---

## Endpoint 1: Generate Campaign (One-Shot)

### POST /v1/marketing/generate

**Purpose**: Accept a brief, return full strategy + solution portfolio in one call.

### Request

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "product_name": "Pain au levain artisanal",
  "product_description": "Sourdough bread baked fresh daily, 100% natural ingredients, no preservatives",
  "product_category": "food_artisan",
  
  "objective": "sales",
  "campaign_timeline": "2 weeks",
  
  "audience": {
    "age_range": "25-50",
    "location": "Tunis",
    "interests": ["baking", "organic_food", "healthy_living"],
    "segment": "premium"
  },
  
  "budget_constraint": {
    "low": 100,
    "high": 1000,
    "currency": "TND"
  },
  
  "language_preference": "bilingual",
  "tone_preference": null,
  "constraints": "Must highlight handmade, no mass production claims",

  "input_media": [
    {
      "asset_type": "image",
      "asset_url": "https://cdn.example.com/uploads/bread_product.jpg",
      "asset_role": "reference_product"
    }
  ],

  "creative_requirements": {
    "generate_images": true,
    "generate_video_storyboard": true,
    "brand_style": "warm artisan, local Tunis feel",
    "aspect_ratio": "4:5"
  }
}
```

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  
  "strategy": {
    "positioning": "Position as artisan quality in a market dominated by industrial bread. Emphasize daily fresh baking and natural ingredients.",
    "target_psychology": "Premium buyers fear added chemicals and mass production. They trust handmade, local, and transparent processes.",
    "market_opportunity": "Ramadan approaching - demand for fresh bread peaks in early mornings. Social media trending more food prepping content.",
    "messaging_pillars": [
      "Handmade daily in Tunis",
      "100% natural, no additives",
      "Support local artisans"
    ],
    "tone_recommendation": "storytelling",
    "channel_priorities": ["instagram", "whatsapp", "email"],
    "timeline_summary": "2 weeks to activate, primary push in week 1",
    "risk_notes": ["Ramadan changes eating patterns", "Climate affects ingredient quality"]
  },
  
  "solutions": [
    {
      "id": "sol_001",
      "index": 0,
      "channel": "social_media",
      "solution_name": "Instagram Reels + Stories Storytelling",
      "description": "Daily behind-the-scenes Reels showing hand-kneading, oven shots, fresh bread moments. Stories for urgent promotions.",
      
      "execution": {
        "content_format": "video_reels",
        "message": "Show the craft, show the freshness, show the passion",
        "assets_needed": ["phone_camera", "smartphone_tripod", "basic_editing"],
        "timeline": "Day 1-2: shoot 10 Reels, Day 3+: daily stories",
        "frequency": "2 Reels per day, 4 Stories per day",
        "posting_windows": [
          {"day": "Monday-Friday", "time": "07:00-08:00", "reason": "Morning coffee scroll, pre-work breakfast decision"},
          {"day": "Friday-Saturday", "time": "18:00-19:00", "reason": "Weekend prep, dinner party planning"},
          {"day": "Daily", "time": "12:30", "reason": "Lunch break, impulse buying moment"}
        ]
      },
      
      "budget": {
        "total_low": 50,
        "total_high": 300,
        "currency": "TND",
        "breakdown": {
          "content_creation": 50,
          "instagram_ads_boost": 150,
          "content_tools": 20,
          "time_management": 80
        }
      },
      
      "expected_outcomes": {
        "reach": "5k-20k",
        "engagement_rate": "4-7%",
        "website_clicks": "50-150",
        "conversion_assumption": "2-5%",
        "roi_estimate": "4x-8x"
      },
      
      "confidence_score": 0.88,
      "reasoning": "Instagram Reels are Instagram's current priority algorithm. Storytelling content outperforms promotional. Your target audience (premium, Tunis-based) is active on Instagram 18:00-21:00.",
      "signals_used": ["ramadan_food_trend", "instagram_reels_algorithm_2026", "tunis_afternoon_peak"],
      "risk_level": "low"
    },
    
    {
      "id": "sol_002",
      "index": 1,
      "channel": "email",
      "solution_name": "Weekly Newsletter + Offers",
      "description": "Collect emails via website/checkout. Send weekly newsletter with baking tips, special offers, new flavors.",
      
      "execution": {
        "content_format": "email",
        "message": "Weekly digest: tips, recipes, 20% weekend promo",
        "assets_needed": ["email_list", "email_template", "product_photos"],
        "timeline": "Collect 100 emails by Day 3, send first newsletter Day 4",
        "frequency": "1 email per week, 1 promo email per month"
      },
      
      "budget": {
        "total_low": 0,
        "total_high": 100,
        "currency": "TND",
        "breakdown": {
          "email_platform": 0,
          "design_template": 50,
          "management": 50
        }
      },
      
      "expected_outcomes": {
        "reach": "100-500 subscribers",
        "open_rate": "25-35%",
        "click_rate": "3-5%",
        "conversion_rate": "5-10%",
        "roi_estimate": "8x-15x"
      },
      
      "confidence_score": 0.82,
      "reasoning": "Email has highest ROI of any channel. Your product is repeat-purchase (people buy bread weekly). Email lets you stay top-of-mind at low cost.",
      "signals_used": ["email_roi_best_practice", "repeat_purchase_category"],
      "risk_level": "low"
    },
    
    {
      "id": "sol_003",
      "index": 2,
      "channel": "whatsapp",
      "solution_name": "WhatsApp Broadcast + Direct Orders",
      "description": "Use WhatsApp Business to announce daily availability, take custom orders, share recipes. Leverage WhatsApp as primary platform in Tunisia.",
      
      "execution": {
        "content_format": "message",
        "message": "Daily '07:00 freshly baked available' + order links",
        "assets_needed": ["whatsapp_business_account", "simple_catalog"],
        "timeline": "Day 1 setup, Day 2 send test",
        "frequency": "2-3 messages per day (morning batch ready, evening restock)"
      },
      
      "budget": {
        "total_low": 0,
        "total_high": 50,
        "currency": "TND",
        "breakdown": {
          "whatsapp_business": 0,
          "catalog_creation": 20,
          "management": 30
        }
      },
      
      "expected_outcomes": {
        "reach": "50-200 members",
        "response_rate": "20-40%",
        "orders_per_week": "20-50",
        "average_order_value": "12-20 TND",
        "roi_estimate": "10x+"
      },
      
      "confidence_score": 0.90,
      "reasoning": "WhatsApp is THE communication platform in Tunisia. Multiple daily touches keeps your bread top-of-mind. Direct order links = instant conversion. Lowest friction.",
      "signals_used": ["tunisia_whatsapp_adoption_98%", "impulse_purchase_category"],
      "risk_level": "low"
    },
    
    {
      "id": "sol_004",
      "index": 3,
      "channel": "partnerships",
      "solution_name": "Cafe + Restaurant Partnerships",
      "description": "Partner with 5-10 cafes/restaurants in Tunis. They sell your bread, you provide 20% margin. You get foot traffic, they get fresh daily supply.",
      
      "execution": {
        "content_format": "b2b_partnership",
        "message": "Partnership proposal: we deliver fresh daily at 06:00",
        "assets_needed": ["packaging", "delivery_system", "simple_contract"],
        "timeline": "Day 1-2: identify targets, Day 3-5: pitch, Day 6: first delivery",
        "frequency": "1x daily delivery to each partner"
      },
      
      "budget": {
        "total_low": 200,
        "total_high": 800,
        "currency": "TND",
        "breakdown": {
          "packaging_upgrade": 200,
          "delivery_logistics": 400,
          "marketing_materials": 100,
          "initial_inventory_boost": 100
        }
      },
      
      "expected_outcomes": {
        "new_outlets": "5-10",
        "volume_increase": "30-50%",
        "revenue_per_outlet": "500-1000 TND/month",
        "roi_estimate": "2x-3x (but cumulative)"
      },
      
      "confidence_score": 0.75,
      "reasoning": "High-effort but high-scale. Gets your product in front of captive audiences daily. Ramadan = peak cafe traffic. Lower confidence because depends on relationship-building.",
      "signals_used": ["ramadan_cafe_peak", "b2b_food_channel"],
      "risk_level": "medium"
    },
    
    {
      "id": "sol_005",
      "index": 4,
      "channel": "paid_ads",
      "solution_name": "Facebook + Instagram Ads (Micro Budget)",
      "description": "Small daily budget ($2-3/day) targeted to Tunis women 25-50, interested in food/health. Retarget site visitors.",
      
      "execution": {
        "content_format": "carousel_ads",
        "message": "Carousel: fresh bread → happy family → order button",
        "assets_needed": ["5 product photos", "simple_copies"],
        "timeline": "Day 1 setup, Day 2 launch",
        "frequency": "Continuous, auto-optimized"
      },
      
      "budget": {
        "total_low": 100,
        "total_high": 500,
        "currency": "TND",
        "breakdown": {
          "ad_spend": 300,
          "design": 50,
          "management": 150
        }
      },
      
      "expected_outcomes": {
        "reach": "10k-30k",
        "cpc": "0.5-1 TND",
        "conversion_rate": "1-3%",
        "cost_per_conversion": "7-20 TND",
        "roi_estimate": "2x-4x"
      },
      
      "confidence_score": 0.70,
      "reasoning": "Paid ads amplify organic reach. Small budget minimizes risk. Good for testing audience response.",
      "signals_used": ["facebook_cpm_tunisia", "retargeting_best_practice"],
      "risk_level": "medium"
    },
    
    {
      "id": "sol_006",
      "index": 5,
      "channel": "content",
      "solution_name": "Blog + SEO: Sourdough Craftsmanship",
      "description": "Write 2-3 blog posts (10-minute reads) about sourdough history, fermentation science, health benefits. Rank for 'pain artisanal Tunis', 'sourdough health'.",
      
      "execution": {
        "content_format": "blog_post",
        "message": "Educational content that builds trust + captures search traffic",
        "assets_needed": ["blog_platform", "3 posts (500 words each)", "seo_optimization"],
        "timeline": "2 weeks to write + optimize",
        "frequency": "1 post every 2 weeks"
      },
      
      "budget": {
        "total_low": 50,
        "total_high": 300,
        "currency": "TND",
        "breakdown": {
          "blog_platform": 20,
          "seo_tools": 30,
          "writing_or_copywriting": 250
        }
      },
      
      "expected_outcomes": {
        "organic_reach_3m": "500-2000",
        "leads_from_blog": "10-30",
        "roi_estimate": "5x+ (if sustained)"
      },
      
      "confidence_score": 0.65,
      "reasoning": "Slow burn. Long-tail keywords (artisan bread Tunisia) have low competition. Good for brand authority. Lower priority than immediate sales channels.",
      "signals_used": ["seo_artisan_food", "content_roi_longterm"],
      "risk_level": "low_but_slow"
    },
    
    {
      "id": "sol_007",
      "index": 6,
      "channel": "events",
      "solution_name": "Ramadan Market Pop-Up",
      "description": "Rent a small booth at Ramadan food markets (Medina, Carrefour) for 4 weeks. Daily sampling + sales.",
      
      "execution": {
        "content_format": "offline_experience",
        "message": "Let customers taste the difference",
        "assets_needed": ["booth_rental", "sampling_inventory", "signage"],
        "timeline": "Arrange by mid-February, operate Ramadan month",
        "frequency": "Open daily 15:00-21:00 (fasting hours)"
      },
      
      "budget": {
        "total_low": 500,
        "total_high": 1500,
        "currency": "TND",
        "breakdown": {
          "booth_rental": 800,
          "sampling_inventory": 400,
          "staff": 300
        }
      },
      
      "expected_outcomes": {
        "foot_traffic": "5k-15k",
        "conversion_rate": "1-2%",
        "revenue": "2000-5000 TND",
        "brand_awareness": "High in Tunis"
      },
      
      "confidence_score": 0.80,
      "reasoning": "Ramadan peak demand. Direct customer interaction. High cost but guaranteed foot traffic.",
      "signals_used": ["ramadan_food_peak", "market_foot_traffic"],
      "risk_level": "medium"
    }
  ],
  
  "portfolio_summary": {
    "total_solutions": 7,
    "channels_covered": ["social_media", "email", "whatsapp", "partnerships", "paid_ads", "content", "events"],
    "budget_range": {
      "minimum_portfolio": 400,
      "balanced_portfolio": 800,
      "aggressive_portfolio": 1500
    },
    "recommended_quick_wins": ["whatsapp", "email"],
    "recommended_scale_plays": ["partnerships", "ramadan_market"]
  },
  
  "market_signals_used": [
    {
      "signal": "Ramadan starts March 30",
      "type": "event",
      "impact": "Peak demand for fresh bread, early morning coffee culture explodes"
    },
    {
      "signal": "Instagram Reels algorithm 2026 prioritizes video",
      "type": "trend",
      "impact": "Storytelling video content 3x more reach than static"
    },
    {
      "signal": "WhatsApp adoption in Tunisia = 98%",
      "type": "market_fact",
      "impact": "WhatsApp is fastest channel to customer"
    }
  ],

  "visual_insights": [
    {
      "asset_id": "asset_001",
      "composition_score": 0.81,
      "brand_consistency_score": 0.74,
      "cta_readability_score": 0.62,
      "recommendations": [
        "Increase CTA contrast in lower-right area",
        "Add product close-up for texture emphasis"
      ]
    }
  ],

  "generated_assets": {
    "images": [
      {
        "media_id": "img_001",
        "format": "png",
        "url": "https://cdn.example.com/generated/img_001.png",
        "prompt_used": "artisan bread, warm lighting, Tunis bakery style, visible CTA"
      }
    ],
    "video_storyboard": {
      "title": "Fresh Bread Morning Hook",
      "duration_seconds": 20,
      "shots": [
        {"shot": 1, "duration": 4, "description": "Close-up crust crack sound"},
        {"shot": 2, "duration": 6, "description": "Baker preparing dough"},
        {"shot": 3, "duration": 6, "description": "Family breakfast table"},
        {"shot": 4, "duration": 4, "description": "CTA with order instructions"}
      ]
    }
  },
  
  "next_actions": [
    "Start with WhatsApp broadcast (lowest friction, immediate orders)",
    "Launch email list collection on website/checkout",
    "Shoot 5-10 Instagram Reels this week",
    "Pitch 3 target cafes for partnerships"
  ],
  
  "confidence_overall": 0.82,
  "generation_latency_ms": 4200,
  "created_at": "2026-04-11T10:30:45Z"
}
```

---

## Endpoint 2: Refine Solutions

### POST /v1/marketing/refine

**Purpose**: Modify previous results without starting from scratch.

### Request

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "refinement_instruction": "Remove the blog option, add TikTok instead. Make email budget lower.",
  "updated_budget_constraint": {
    "low": 100,
    "high": 700
  }
}
```

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "refinement_id": "ref_001",
  
  "removed_solutions": ["sol_006"],
  
  "new_solutions": [
    {
      "id": "sol_008",
      "index": 6,
      "channel": "social_media",
      "solution_name": "TikTok Viral Bread Trends",
      "description": "Tap into #FoodTok. Post short clips (15-30s) of bread being cut, crumb texture, morning fresh moments. Easy to go viral.",
      
      "execution": {
        "content_format": "short_video",
        "message": "ASMR bread cutting, crumb showcase, morning vibes"
      },
      
      "budget": {
        "total_low": 80,
        "total_high": 200,
        "currency": "TND",
        "breakdown": {
          "content_creation": 50,
          "posting_tools": 30,
          "optional_ads": 120
        }
      },
      
      "confidence_score": 0.75,
      "reasoning": "TikTok audience skews young but expanding in Tunisia. Bread/food content goes viral easily. Organic reach is high if content quality good."
    }
  ],
  
  "modified_solutions": [
    {
      "id": "sol_002",
      "modified_field": "budget",
      "old_value": {"total_low": 0, "total_high": 100},
      "new_value": {"total_low": 0, "total_high": 50}
    }
  ],
  
  "new_portfolio_summary": {
    "total_solutions": 7,
    "channels_covered": ["social_media", "email", "whatsapp", "partnerships", "paid_ads", "events", "tiktok"]
  },
  
  "created_at": "2026-04-11T10:45:30Z"
}
```

---

## Endpoint 3: Get Campaign

### GET /v1/marketing/campaign/{campaign_id}

**Purpose**: Retrieve full campaign details (brief + strategy + solutions).

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generated",
  
  "brief": { /* full campaign_briefs table row */ },
  "strategy": {
    /* full campaign_strategies row */
    "model_used": "groq:llama-3.3-70b-versatile",
    "latency_ms": 1200,
    "tokens_used": 300
  },
  "solutions": [
    {
      /* campaign_solutions row */
      "model_used": "groq:llama-3.3-70b-versatile",
      "latency_ms": 1400
    }
  ],
  
  "refinements": [
    { "refinement_id": "ref_001", "instruction": "..." }
  ],
  
  "created_at": "2026-04-11T10:30:45Z",
  "updated_at": "2026-04-11T10:45:30Z"
}
```

Contract freeze note:
- For n8n integration phase, treat Endpoint 1, 3, 5, 10, and 11 payload shapes as frozen unless a blocker appears.

---

## Endpoint 4: Submit Feedback

### POST /v1/marketing/feedback

**Purpose**: Log user action (chose solution, edited, published, measured result).

### Request

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "solution_id": "sol_003",
  
  "feedback_type": "selected",
  "selected": true,
  "edited_content": "Added phone number to WhatsApp broadcast",
  
  "published": true,
  "published_url": "https://wa.me/21622345678",
  
  "performance": {
    "impressions": 150,
    "clicks": 25,
    "conversions": 5,
    "engagement_count": 30
  },
  
  "user_notes": "Great result, customers loved the daily updates!"
}
```

### Response (200 OK)

```json
{
  "feedback_id": "fb_001",
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "solution_id": "sol_003",
  "learning_update": {
    "message": "WhatsApp storytelling tone: updated to high-confidence (0.92)",
    "updated_in_brand_memory": true
  },
  "created_at": "2026-04-11T11:00:00Z"
}
```

---

## Endpoint 5: Get Market Signals (Transparency)

### GET /v1/marketing/signals?region=tunisia&signal_type=event

**Purpose**: Show what data is influencing generation (demo storytelling).

### Response (200 OK)

```json
{
  "signals": [
    {
      "id": "sig_001",
      "region": "tunisia",
      "signal_type": "event",
      "signal_key": "ramadan_2026",
      "signal_value": "Ramadan 2026: March 30 - April 28",
      "confidence": 1.0,
      "tags": {"category": "food", "urgency": "high", "duration": "4_weeks"},
      "fetched_at": "2026-04-10T00:00:00Z",
      "expires_at": "2026-04-29T00:00:00Z"
    },
    {
      "id": "sig_002",
      "region": "mena",
      "signal_type": "trend",
      "signal_key": "instagram_reels_algorithm",
      "signal_value": "Instagram prioritizes Reels in feed (2026 algorithm update)",
      "confidence": 0.95
    }
  ],
  "count": 2,
  "fetched_at": "2026-04-11T09:00:00Z"
}
```

---

## Endpoint 6: Unified Multimodal Chat

### POST /v1/marketing/chat

**Purpose**: Accept user chat input with text + optional images and return strategy/creative guidance in one assistant response.

### Request (multipart/form-data or JSON)

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "chat_sess_001",
  "message": "How can I improve this product poster and launch a campaign this week?",
  "attached_assets": [
    {
      "asset_type": "image",
      "asset_url": "https://cdn.example.com/uploads/poster_v1.jpg"
    }
  ]
}
```

### Response (200 OK)

```json
{
  "session_id": "chat_sess_001",
  "assistant_message": "Your poster has strong product visibility but weak CTA contrast. I suggest a 3-channel launch with one revised visual.",
  "visual_insights": [
    {"asset_id": "asset_101", "issues": ["Low CTA contrast"], "quick_fixes": ["Use high-contrast CTA button"]}
  ],
  "recommended_solutions": ["whatsapp", "instagram_reels", "email"],
  "next_actions": ["Generate revised visual", "Schedule WhatsApp broadcast"]
}
```

---

## Endpoint 7: Analyze Media Asset

### POST /v1/marketing/media/analyze

**Purpose**: Extract structured visual diagnostics from uploaded marketing assets.

### Request

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_url": "https://cdn.example.com/uploads/poster_v1.jpg",
  "objective": "sales",
  "platform": "instagram"
}
```

### Response (200 OK)

```json
{
  "asset_id": "asset_201",
  "scores": {
    "composition": 0.79,
    "brand_consistency": 0.72,
    "cta_clarity": 0.58
  },
  "detected_issues": ["CTA text blends into background"],
  "improvement_actions": ["Increase CTA contrast", "Move CTA above fold"]
}
```

---

## Endpoint 8: Generate Campaign Image

### POST /v1/marketing/media/generate-image

**Purpose**: Generate campaign-ready image variants from strategy and style constraints.

### Request

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "prompt": "Artisan bread on warm wooden table, early morning Tunis lighting, clear CTA",
  "aspect_ratio": "4:5",
  "variants": 2
}
```

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "generated_images": [
    {"media_id": "img_301", "url": "https://cdn.example.com/generated/img_301.png"},
    {"media_id": "img_302", "url": "https://cdn.example.com/generated/img_302.png"}
  ]
}
```

---

## Endpoint 9: Generate Video Plan (Storyboard)

### POST /v1/marketing/media/generate-video-plan

**Purpose**: Generate a short-form video storyboard and script. Rendering is optional and can run asynchronously.

### Request

```json
{
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "objective": "engagement",
  "platform": "instagram_reels",
  "duration_seconds": 20
}
```

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "storyboard": {
    "hook": "The bread crack sound in first 2 seconds",
    "shots": [
      {"shot": 1, "duration": 4, "description": "Close-up crust break"},
      {"shot": 2, "duration": 6, "description": "Preparation process"},
      {"shot": 3, "duration": 6, "description": "Customer reaction"},
      {"shot": 4, "duration": 4, "description": "CTA and order path"}
    ],
    "voiceover_script": "Fresh every morning in Tunis. Order now for same-day pickup."
  },
  "render_status": "planned"
}
```

---

## Endpoint 10: POST /v1/marketing/generate/stream

**Purpose**: Stream generation progress as NDJSON for better demo UX and transparency.

### Request Body
Same schema as `/v1/marketing/generate`.

### Response (200 OK, `application/x-ndjson`)

```json
{"status":"analyzing","step":"reading_market_signals","data":{"workspace_id":"11111111-1111-1111-1111-111111111111"},"timestamp":"2026-04-12T10:05:11Z"}
{"status":"signals_ready","step":"signals_loaded","data":{"signals_count":17},"timestamp":"2026-04-12T10:05:11Z"}
{"status":"strategy_ready","step":"strategy_generated","data":{"strategy":{"positioning":"..."}},"timestamp":"2026-04-12T10:05:12Z"}
{"status":"solutions_ready","step":"portfolio_generated","data":{"solutions_count":7,"channels":["email","social_media","whatsapp"]},"timestamp":"2026-04-12T10:05:13Z"}
{"status":"completed","step":"generation_complete","data":{"campaign_id":"660e8400-e29b-41d4-a716-446655440001"},"timestamp":"2026-04-12T10:05:14Z"}
```

---

## Endpoint 11: POST /v1/marketing/media/generate-creative-brief

**Purpose**: Return a reliable provider-free creative brief (prompt + design guidance) for Canva/designer execution.

### Request Body

```json
{
  "workspace_id": "11111111-1111-1111-1111-111111111111",
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "product_name": "Pain au levain artisanal",
  "objective": "sales",
  "channel": "social_media",
  "audience": {
    "location": "Tunis"
  },
  "language_preference": "bilingual",
  "tone_preference": "storytelling",
  "style_constraints": ["warm tones", "close-up product shot"],
  "reference_notes": "highlight same-day pickup"
}
```

### Response (200 OK)

```json
{
  "campaign_id": "660e8400-e29b-41d4-a716-446655440001",
  "objective": "sales",
  "channel": "social_media",
  "image_prompt": "Pain au levain artisanal campaign visual in Tunis, storytelling tone, warm tones, close-up product shot, objective: sales, platform: social_media, aspect ratio 4:5, high clarity and local cultural context. Reference notes: highlight same-day pickup.",
  "canva_template_suggestion": "Instagram Food Story - Warm Tones",
  "color_palette": ["#8B4513", "#F5DEB3", "#2E8B57"],
  "text_overlay": "Pain au levain artisanal - Frais chaque matin | طازج كل صباح",
  "do_not_include": [
    "industrial factory scenes",
    "low-resolution visuals",
    "overcrowded text",
    "misleading pricing claims"
  ],
  "recommended_aspect_ratio": "4:5",
  "rationale": "Structured creative brief is stable for hackathon demos, avoids provider failures, and remains directly usable in Canva or design tools."
}
```

---

## Error Responses

All endpoints follow this error contract:

```json
{
  "error": {
    "code": "INVALID_BUDGET",
    "message": "Budget constraint_low must be < constraint_high",
    "details": {
      "field": "budget_constraint",
      "value": {"low": 1000, "high": 500}
    }
  },
  "status": 400,
  "timestamp": "2026-04-11T10:30:45Z"
}
```

Common codes:
- `INVALID_BRIEF`: Missing required fields
- `WORKSPACE_NOT_FOUND`: workspace_id doesn't exist
- `LLM_TIMEOUT`: Generation took >10s, giving up
- `INSUFFICIENT_SIGNALS`: Market data too stale
- `RATE_LIMIT`: Too many requests
- `UNSUPPORTED_MEDIA_TYPE`: Media format not supported
- `ASSET_TOO_LARGE`: Uploaded image/video exceeds configured size
- `MEDIA_GENERATION_FAILED`: External generation provider failed

---

## Implementation Checklist

- [ ] Define Pydantic models for all request/response schemas
- [ ] Implement input validation (budget, language, objective)
- [ ] Build route handlers for all 11 endpoints (or 9 core + 2 reliability quick-wins)
- [ ] Add error handling + custom exceptions
- [ ] Add request/response logging
- [ ] Generate OpenAPI docs
- [ ] Test all endpoints locally
- [ ] Document timeout behavior
