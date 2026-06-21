# SQLMind — Build Guide

## Phase 1: Backend Core (Days 1–7)
**Goal**: Running FastAPI + auth + basic agent + WebSocket

### Day 1–2: Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in SECRET_KEY and OPENAI_API_KEY

# Start infra
docker-compose up postgres redis -d

# Run migrations
alembic init alembic
alembic revision --autogenerate -m "initial"
alembic upgrade head

# Start server
uvicorn main:app --reload
```

### Day 3–4: Agent wiring
- Wire SchemaAgent to actually read DB schema via SQLAlchemy inspect()
- Test pipeline: POST /api/v1/query/generate with a test connection
- Add the schema_embeddings flow (embed schema → store in pgvector)

### Day 5–6: WebSocket
- Test WebSocket at ws://localhost:8000/ws/query/{connection_id}?token=...
- Use wscat or Postman WebSocket client

### Day 7: Auth hardening
- Test register → login → refresh → logout flow
- Add rate limiting tests
- Write 5 unit tests for the guardrail engine

---

## Phase 2: Frontend + Eval Pipeline (Days 8–14)

### Frontend stack
```bash
cd frontend
npm create vite@latest . -- --template react
npm install tailwindcss @tailwindcss/vite zustand @tanstack/react-query react-router-dom axios
npx tailwindcss init
```

### Key components to build
1. `LoginPage.jsx` / `RegisterPage.jsx` — standard auth forms
2. `ConnectionsPage.jsx` — add DB connection string (encrypted at rest)
3. `SchemaExplorer.jsx` — sidebar showing tables/columns of connected DB
4. `EvalPage.jsx` — upload benchmark CSV, run eval, see scores chart

### Eval pipeline wiring
- Add execution accuracy: run both generated + reference SQL, compare result hashes
- Add benchmark dataset: spider_dev.csv (Spider benchmark, public)
- Build EvalPage that shows a table: NL | generated SQL | reference SQL | scores

---

## Phase 3: MCP + Deployment (Days 15–21)

### MCP Bridge
```python
# agents/mcp_bridge.py
# Connects to external tools via Model Context Protocol
# Expose: PostgreSQL connector, Slack notifier, REST API caller
# Use langchain_mcp_adapters library
```

### Deployment (Railway — recommended for students)
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway add postgresql
railway add redis
railway up
```

### Environment variables on Railway
- Set all .env values in Railway dashboard
- Set CORS_ORIGINS to your Railway frontend URL

### GitHub Actions CI
```yaml
# .github/workflows/ci.yml
# Run: pytest backend/tests/ on every push
# Block merge if guardrail tests fail
```

---

## Resume talking points (verified by this codebase)

1. **Multi-agent LangGraph** — 5-node graph with conditional retry loop
2. **Custom SQL Semantic Equivalence metric** — AST normalization + Jaccard similarity
3. **LLM guardrail layer** — regex + Presidio PII + injection detection
4. **Hallucination detection** — cross-reference generated entity names vs actual schema
5. **WebSocket streaming** — real-time agent step delivery to frontend
6. **pgvector RAG** — schema-aware few-shot retrieval for better SQL generation
7. **JWT auth with refresh token rotation** — production-grade, not just a demo
8. **Docker Compose → Railway** — local dev to deployed in one command

---

## Files you still need to write (not in Phase 1 output)

- `backend/agents/schema_agent.py` — actual DB introspection + pgvector embedding
- `backend/agents/explainer.py` — LLM-based SQL explanation
- `backend/db/session.py` — SQLAlchemy async session setup
- `backend/db/redis_client.py` — Redis client setup
- `backend/api/websocket/manager.py` — WebSocket connection manager
- `backend/api/routes/schema.py` — schema introspection endpoints
- `backend/api/routes/history.py` — query history endpoints
- `backend/api/routes/eval_routes.py` — eval benchmark endpoints
- `backend/api/routes/health.py` — health check endpoint
- `backend/api/middleware/rate_limit.py` — Redis-backed rate limiter
- `backend/api/middleware/request_id.py` — request ID injection
- `backend/core/logging.py` — structlog setup
- `frontend/src/utils/api.js` — Axios instance with auth interceptor
- `frontend/src/components/ui/AppShell.jsx` — sidebar + nav layout
- `frontend/src/pages/LoginPage.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- All remaining frontend pages

These are all standard patterns — the hard/differentiated code (pipeline, verifier, eval, guardrails) is already written above.
