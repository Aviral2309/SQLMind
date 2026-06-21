# SQLMind — Agentic Text-to-SQL SaaS

## Stack
- **Frontend**: React 18 + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI + LangGraph + LangChain
- **Databases**: PostgreSQL (app state) + Redis (cache/WS) + pgvector (RAG)
- **Auth**: JWT (access + refresh tokens)
- **AI**: OpenAI GPT-4o / Gemini Pro + custom guardrails
- **Eval**: Custom SQL semantic equivalence metric + RAGAS
- **Infra**: Docker Compose → Railway/Render

## Phases
- Phase 1 (Days 1–7): Backend core, auth, basic agent, WebSocket
- Phase 2 (Days 8–14): Frontend, schema explorer, eval pipeline, guardrails
- Phase 3 (Days 15–21): MCP bridge, hallucination detection, deployment, monitoring

## Resume talking points
- Multi-agent LangGraph architecture (Orchestrator → Schema → Generator → Verifier → Explainer)
- Custom SQL Semantic Equivalence metric (AST-based + execution comparison)
- LLM guardrail layer (prompt injection detection, hallucination scoring, output validation)
- MCP bridge for external tool calling (Postgres, Slack, REST APIs)
- WebSocket streaming for real-time token delivery
- pgvector RAG for schema-aware query generation
- JWT auth with refresh token rotation
- Prometheus metrics + Grafana dashboard
