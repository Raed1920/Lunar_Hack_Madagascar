# End-to-End Example (Dynamic Agent Pipeline)

## Request
```json
POST /chat
{
  "user_id": "user-123",
  "session_id": "sess-001",
  "language": "en",
  "message": "Our SaaS churn is rising and CAC is increasing. I need a decision for next quarter."
}
```

## Internal Agent Flow (Example)

### Intent Agent
```json
{
  "intent": "optimize",
  "domain": "analytics",
  "confidence": 0.86,
  "concern_area": "strategy",
  "urgency": "high",
  "requires_rag": true
}
```

### Schema Builder Agent
```json
{
  "required_fields": [
    "goal",
    "north_star_metric",
    "data_availability",
    "timeline"
  ],
  "field_descriptions": {
    "goal": "Primary business outcome",
    "north_star_metric": "Main metric to optimize",
    "data_availability": "Availability of clean tracking data",
    "timeline": "Decision and execution horizon"
  }
}
```

### Qualification Agent
```json
{
  "updated_profile": {
    "goal": "Reduce churn while improving CAC efficiency",
    "timeline": "next quarter"
  },
  "missing_fields": [
    "north_star_metric",
    "data_availability"
  ],
  "next_question": "Which single KPI should be the north-star for this quarter?"
}
```

### RAG Agent
```json
{
  "factual_response": "Benchmark evidence suggests retention interventions with weekly cohort tracking can reduce churn 8-15% in one quarter.",
  "citations": [
    "marketing_guides.md",
    "faqs.md"
  ],
  "grounded": true,
  "confidence": "high",
  "uncertainty": ""
}
```

### Recommendation Agent
```json
{
  "recommended_strategy": "Run a retention-first growth loop with lifecycle campaigns and churn-risk interventions.",
  "actions": [
    "Define churn-risk cohort rules and weekly review",
    "Launch win-back and onboarding lifecycle campaigns",
    "Shift 20% CAC spend from low-LTV segments to high-retention segments"
  ],
  "expected_impact": "8-15% churn reduction and improved CAC payback within one quarter",
  "decision_options": [
    {
      "title": "Retention Focus",
      "summary": "Prioritize churn reduction before new acquisition scale",
      "tradeoff": "Slower top-line growth in the first month"
    },
    {
      "title": "Balanced Mix",
      "summary": "Run retention and acquisition in parallel",
      "tradeoff": "Higher coordination and execution complexity"
    }
  ],
  "risks": [
    "Incomplete attribution data",
    "Execution bandwidth"
  ]
}
```

### Decision Agent
```json
{
  "action": "Start retention-first execution for 6 weeks before scaling acquisition",
  "priority": "high",
  "justification": "High urgency and strong confidence with immediate impact on churn and CAC efficiency.",
  "steps": [
    "Assign decision owner and KPI dashboard",
    "Deploy churn-risk triggers and lifecycle playbooks",
    "Review cohort movement weekly and rebalance spend"
  ],
  "priority_score": 82
}
```

## API Response (Example)
```json
{
  "response": "Recommended direction: run a retention-first growth loop. Decision: start a 6-week retention-first execution sprint (priority high). Key risk: incomplete attribution data. Which single KPI should be your north-star this quarter?",
  "language": "en",
  "structured": {
    "business_type": "saas",
    "need": "Reduce churn while improving CAC efficiency",
    "recommended_strategy": "Run a retention-first growth loop with lifecycle campaigns and churn-risk interventions.",
    "estimated_impact": "8-15% churn reduction and improved CAC payback within one quarter",
    "cta": "Start retention-first execution for 6 weeks before scaling acquisition",
    "lead_score": 81,
    "concern_area": "strategy",
    "urgency": "high",
    "priority_actions": [
      "Define churn-risk cohort rules and weekly review",
      "Launch win-back and onboarding lifecycle campaigns",
      "Shift 20% CAC spend from low-LTV segments to high-retention segments"
    ],
    "missing_fields": [
      "north_star_metric",
      "data_availability"
    ]
  },
  "user_profile": {
    "domain": "analytics",
    "required_fields": [
      "goal",
      "north_star_metric",
      "data_availability",
      "timeline"
    ],
    "priority": "high",
    "priority_score": 82,
    "dynamic_profile": {
      "goal": "Reduce churn while improving CAC efficiency",
      "timeline": "next quarter"
    }
  },
  "rag_sources": [
    "marketing_guides.md",
    "faqs.md"
  ],
  "next_question": "Which single KPI should be the north-star for this quarter?"
}
```
