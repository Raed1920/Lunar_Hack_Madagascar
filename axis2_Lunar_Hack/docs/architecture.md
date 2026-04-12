# Adaptive AI Decision Engine - Architecture

## System Diagram

```mermaid
flowchart LR
    subgraph UI[Frontend - React]
        U1[Chat Interface]
        U2[Decision Snapshot]
        U3[Action Panels]
    end

    subgraph API[Backend - FastAPI]
        A1[POST /chat]
        A2[Dynamic Orchestrator]
        A3[Session Memory]
        A4[Profile Memory SQLite]
    end

    subgraph AGENTS[Modular Agent Layer]
        I1[Intent Agent]
        I2[Schema Builder Agent]
        I3[Qualification Agent]
        I4[RAG Agent]
        I5[Recommendation Agent]
        I6[Decision Agent]
        I7[Response Agent]
    end

    subgraph KNOWLEDGE[RAGFlow]
        K1[Dataset Retrieval]
        K2[Chunk Evidence]
    end

    subgraph LLM[Ollama]
        L1[Fast Model]
        L2[Reasoning Model]
    end

    U1 --> A1
    U2 --> A1
    U3 --> A1

    A1 --> A2
    A2 --> A3
    A2 --> A4

    A2 --> I1
    I1 --> I2
    I2 --> I3
    I3 --> I4
    I4 --> K1
    K1 --> K2
    K2 --> I4
    I4 --> I5
    I5 --> I6
    I6 --> I7

    I1 --> L1
    I2 --> L1
    I3 --> L1
    I4 --> L2
    I5 --> L2
    I6 --> L2
    I7 --> L2

    I7 --> A2
    A2 --> U1
    A2 --> U2
```

## Pipeline Flow
1. User message enters the orchestrator.
2. Intent Agent returns normalized intent, domain, urgency, and confidence.
3. Schema Builder Agent produces 3 to 5 dynamic required fields for that context.
4. Qualification Agent extracts known values and asks one high-impact next question.
5. RAG Agent runs only when factual grounding is required.
6. Recommendation Agent generates strategy, options, actions, and expected impact.
7. Decision Agent outputs one admin-facing action, priority, justification, and steps.
8. Response Agent converts structured outputs into concise multilingual response.
9. Orchestrator persists profile and returns structured payload to frontend.

## Dynamic Schema Strategy
- Schema is regenerated every turn from intent + domain + known profile.
- Required fields are limited to 3 to 5 for speed and focus.
- Unknown/invalid fields are sanitized to snake_case and deduplicated.
- Existing profile values reduce missing_fields automatically.
- Dynamic field values are persisted inside profile preferences.dynamic_profile.

## Contract Validation Strategy
- Every agent returns strict JSON.
- JSON is parsed and validated against Pydantic models.
- On invalid JSON, the system retries once with a repair prompt.
- If validation still fails, stage-specific fallback JSON is used.
- Downstream agents always receive validated contracts.

## Scoring
- Lead/readiness score uses dynamic completeness + urgency + confidence + intent.
- Decision priority score combines urgency, confidence, missing data, action count, and risk count.

## Memory Model
- Session memory: interaction history for context windows.
- Long-term memory: profile + preferences in SQLite.
- Dynamic values are stored under preferences.dynamic_profile with required_fields metadata.
