# Adaptive AI Decision Engine (Local)

A local-first multi-agent decision support platform powered by:
- Ollama for local LLM inference
- FastAPI backend
- RAGFlow retrieval layer
- React frontend
- SQLite memory for session + profile context

## What This System Does
- Routes each request with a lightweight deterministic router
- Uses RAG retrieval only when the route requires grounding
- Runs one generation LLM call for recommendation + final response
- Keeps response contract stable for frontend consumption
- Responds in EN, FR, or AR
- Returns strict structured JSON for downstream automation

## Dynamic Agent Pipeline
User Input
-> Router (lightweight)
-> (if needed) RAG retrieval
-> Single Generation Agent

## Architecture Docs
- System architecture: [docs/architecture.md](docs/architecture.md)
- Prompt contract catalog: [docs/sample_prompts.md](docs/sample_prompts.md)
- End-to-end flow example: [docs/e2e_example.md](docs/e2e_example.md)

## Project Structure
```text
backend/
  app/
    agents/
      base.py
      single_generation_agent.py
    router.py
    main.py
    crew_orchestrator.py
    memory.py
    ragflow_client.py
    ollama_client.py
    prompts.py
    models.py
    lead_scoring.py
    utils.py
    config.py
  scripts/
    index_documents.py
    rag_indexer.py
frontend/
  src/
    App.tsx
    api.ts
    types.ts
    styles.css
    main.tsx
docs/
  architecture.md
  sample_prompts.md
  e2e_example.md
```

## Prerequisites
- Python 3.10+
- Node.js 18+
- Ollama running locally
- RAGFlow running locally

## Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:
```bash
curl http://localhost:8000/health
```

## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## RAG Indexing (Local)
```bash
cd backend
python scripts/rag_indexer.py --docs-dir ..\data\sample_docs --base-url http://localhost:9380 --dataset-id sales-kb --create-dataset --embedding-model bge-m3 --verbose
```

## API Contract
### Request
```json
{
  "user_id": "user-123",
  "session_id": "session-abc",
  "message": "Our CAC is rising and churn is high. What should we prioritize?",
  "language": "en"
}
```

### Response Highlights
- response: natural language summary
- structured: strategy + impact + action + missing fields
- user_profile: dynamic_profile + required_fields + decision priority
- rag_sources: factual evidence sources
- next_question: single adaptive follow-up when needed

## Dynamic Schema + Error Handling Strategy
- Each stage uses strict JSON contracts with Pydantic validation.
- On invalid JSON, the stage retries once with a repair prompt.
- If still invalid, it falls back to deterministic stage-safe defaults.
- Schema Builder enforces 3 to 5 required fields, deduped and normalized.
- Qualification recomputes missing fields from merged known profile + extracted values.

## Notes
- All inference is local via Ollama.
- RAG remains optional and conditionally triggered.
- Architecture is modular and each agent has a single responsibility.
