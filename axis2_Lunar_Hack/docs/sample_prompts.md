# Sample Agent Prompts (Dynamic Pipeline)

## 1) Intent Agent
System intent:
- Detect intent + domain + urgency + confidence.
- Decide if RAG grounding is needed.
- Return strict JSON.

Output contract:
- intent
- domain
- confidence
- concern_area
- urgency
- requires_rag
- rationale

## 2) Schema Builder Agent
System intent:
- Build dynamic required fields from intent/domain.
- Keep only 3 to 5 required fields.
- Add field descriptions.

Output contract:
- required_fields
- field_descriptions
- rationale

## 3) Qualification Agent
System intent:
- Extract known values only for dynamic required_fields.
- Return missing_fields.
- Ask exactly one next best question.

Output contract:
- updated_profile
- missing_fields
- next_question

## 4) RAG Agent
System intent:
- Answer from retrieved context only.
- Include citations and uncertainty when needed.
- No hallucination.

Output contract:
- factual_response
- citations
- grounded
- confidence
- uncertainty

## 5) Recommendation Agent
System intent:
- Generate strategy and actions from profile + intent + RAG evidence.
- Provide decision options with tradeoffs.

Output contract:
- recommended_strategy
- actions
- expected_impact
- decision_options
- risks

## 6) Decision Agent
System intent:
- Convert recommendation into one admin action with priority.
- Add practical implementation steps.

Output contract:
- action
- priority
- justification
- steps
- priority_score

## 7) Response Agent
System intent:
- Convert structured contracts into concise multilingual response.
- Ask one follow-up question only when data is missing.

Output contract:
- response
- next_question

## Prompt Design Notes for Local Ollama
- Keep schema contracts short and deterministic.
- Avoid verbose roleplay instructions.
- Use one clear JSON schema per call.
- Add single repair retry when output is invalid JSON.
