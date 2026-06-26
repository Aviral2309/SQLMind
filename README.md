# SQLMind — AI-Powered Text-to-SQL Data Intelligence Platform

[![Live Demo](https://img.shields.io/badge/Live%20Demo-sqlmind--app.vercel.app-blue?style=flat-square)](https://sqlmind-app.vercel.app)
[![Backend](https://img.shields.io/badge/API%20Docs-Render-green?style=flat-square)](https://sqlmind-6wn2.onrender.com/docs)
[![GitHub](https://img.shields.io/badge/GitHub-SQLMind-black?style=flat-square&logo=github)](https://github.com/Aviral2309/SQLMind)

> Ask your database anything in plain English. SQLMind generates, verifies, and executes SQL — then answers your question directly.

---

## Live Demo

| | URL |
|---|---|
| **Frontend** | https://sqlmind-app.vercel.app |
| **API Docs** | https://sqlmind-6wn2.onrender.com/docs |
| **GitHub** | https://github.com/Aviral2309/SQLMind |

---

## What is SQLMind?

SQLMind is a full-stack SaaS platform that converts natural language questions into verified SQL queries, executes them on your database, and returns direct answers — not just code.

**Instead of writing:**
```sql
SELECT c.name, SUM(o.total) as revenue
FROM customers c JOIN orders o ON c.id = o.customer_id
WHERE o.created_at >= DATE_TRUNC('month', NOW())
GROUP BY c.name ORDER BY revenue DESC LIMIT 10;
```

**You just ask:**
> "Who are my top 10 customers by revenue this month?"

---

## Key Features

### Core — 5-Node LangGraph Agent Pipeline

```
Orchestrator → Schema Agent → SQL Generator → Verifier → Explainer
(guardrail)   (pgvector RAG)  (Gemini Flash)  (AST+halluc)  (NL explain)
                                    ↑__________________|
                                    retry loop (max 2×)
```

| Node | What it does |
|---|---|
| **Orchestrator** | Input validation, guardrail check, parallel schema fetch |
| **Schema Agent** | DB introspection, pgvector RAG retrieval, Redis caching |
| **SQL Generator** | NL→SQL with dialect-aware prompting, retry with error context |
| **Verifier** | AST syntax check, safety patterns, hallucination scoring |
| **Explainer** | Plain English explanation of the generated SQL |

### Hallucination Detection
AST-based cross-referencing — extracts every table/column name from generated SQL via sqlglot, cross-checks against actual schema. LLM-invented names get flagged and trigger retry.

### NL-to-Dashboard (Unique Feature)
One sentence → complete multi-panel BI dashboard:
- LLM plans 4–6 widget specs (KPIs, charts, tables)
- All queries execute in parallel
- Auto-selects chart type (line for time-series, bar for categories)
- Renders dashboard — zero configuration

### Auto-Insights
Analyzes any database automatically — no questions needed:
- Row counts, null rates, top values per column
- Time-series trend detection
- Numeric statistics (min/max/avg)
- AI-generated executive summary

### Anomaly Detection
Isolation Forest + Z-score ensemble on query results:
- Detects statistical outliers in any numeric column
- Severity scoring: high / medium / low
- Highlights anomalies on charts

### Query Optimizer
AST-based SQL anti-pattern detection:
- SELECT * on wide tables
- Missing LIMIT clause
- Subqueries in WHERE (rewritable as JOIN)
- Implicit cross joins
- LLM rewrites with explanations

### Custom Eval Metrics
- **SQLSemanticEquivalence** — AST fingerprint + Jaccard similarity
- **BLEU Score** — token-level overlap with reference SQL
- **Hallucination Rate** — % of invented entity names
- **Overall** — weighted combination (40% semantic + 30% execution + 15% BLEU + 15% anti-hallucination)

### Platform
- Conversational chat interface with per-database history
- Two modes: SQL generation OR direct Q&A (executes + answers)
- Results table + auto-chart (line/bar) with table/chart toggle
- JWT auth with refresh token rotation
- LLM guardrails: injection detection, PII (Presidio), off-topic blocking

### Database Support

**Connect via URL:**
- PostgreSQL, MySQL, MariaDB, SQL Server, SQLite

**Upload files:**
- CSV (auto-detects delimiter, infers column types)
- Excel `.xlsx` (each sheet becomes a table)
- SQLite `.db` files
- SQL scripts (auto-executed on fresh SQLite)
- JSON arrays
- TSV files

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Tailwind CSS, Recharts, Zustand, React Query |
| Backend | FastAPI, Python 3.12, Uvicorn |
| AI | LangGraph, LangChain, Google Gemini 1.5 Flash |
| Databases | PostgreSQL + pgvector (RAG), Redis (cache), SQLite |
| SQL Parsing | sqlglot (AST analysis + normalization) |
| ML | scikit-learn (Isolation Forest), NumPy |
| Auth | JWT (python-jose), bcrypt 4.0 |
| Deployment | Render (backend), Vercel (frontend) |
| Monitoring | Prometheus metrics, structlog |

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              React Frontend (Vercel)          │
│  Landing · Chat · Dashboard Builder · Insights│
└───────────────────┬──────────────────────────┘
                    │ HTTPS / WSS
┌───────────────────▼──────────────────────────┐
│           FastAPI Backend (Render)            │
│   JWT · Rate Limit · Guardrails · WebSocket   │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│         LangGraph Agent Pipeline              │
│  5 nodes · parallel execution · retry loop   │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│              Data Layer (Render)              │
│  PostgreSQL + pgvector · Redis · Target DB   │
└──────────────────────────────────────────────┘
```

---

## Local Development

### Prerequisites
- Python 3.12, Node 18+, Docker Desktop

### Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
# Fill SECRET_KEY and GOOGLE_API_KEY

# Start databases
cd ..
docker-compose up postgres redis -d

# Run backend
cd backend
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
echo "VITE_WS_URL=ws://localhost:8000" >> .env
npm run dev
```

- App: http://localhost:5173
- API: http://localhost:8000/docs

---

## Environment Variables

### Backend
```env
SECRET_KEY=your_32_char_secret
GOOGLE_API_KEY=AIza...
DEFAULT_LLM=gemini
LLM_MODEL=gemini-1.5-flash
ASYNC_POSTGRES_URL=postgresql+asyncpg://...
POSTGRES_URL=postgresql://...
REDIS_URL=redis://...
CORS_ORIGINS=["https://sqlmind-app.vercel.app"]
```

### Frontend
```env
VITE_API_URL=https://sqlmind-6wn2.onrender.com
VITE_WS_URL=wss://sqlmind-6wn2.onrender.com
```

---

## Project Structure

```
sqlmind/
├── backend/
│   ├── agents/
│   │   ├── pipeline.py          # LangGraph 5-node graph
│   │   ├── schema_agent.py      # Introspection + pgvector RAG + Redis cache
│   │   ├── sql_generator.py     # NL → SQL, dialect-aware
│   │   ├── verifier.py          # AST + hallucination detection
│   │   ├── explainer.py         # Plain English explanation
│   │   ├── executor.py          # SQL execution on target DB
│   │   ├── answer_agent.py      # Results → NL answer
│   │   ├── anomaly_detector.py  # Isolation Forest + Z-score
│   │   ├── query_optimizer.py   # Anti-pattern detection + LLM rewrite
│   │   ├── insight_agent.py     # Auto database analysis
│   │   └── dashboard_agent.py   # NL-to-Dashboard
│   ├── api/routes/
│   │   ├── auth.py, query.py, schema.py
│   │   ├── history.py, insights.py
│   │   ├── dashboard.py, file_routes.py
│   │   └── upload.py
│   ├── eval/pipeline.py         # Custom eval metrics
│   ├── guardrails/guardrail_engine.py
│   └── main.py
│
└── frontend/src/
    ├── pages/
    │   ├── LandingPage.jsx       # Marketing landing + typewriter
    │   ├── LoginPage.jsx         # Split-layout auth
    │   ├── DashboardPage.jsx     # Overview
    │   ├── QueryPage.jsx         # Chat query interface
    │   ├── DashboardBuilderPage.jsx  # NL-to-Dashboard (unique)
    │   ├── InsightsPage.jsx      # Auto analysis
    │   ├── ConnectionsPage.jsx   # Connect + upload
    │   ├── OptimizerPage.jsx     # SQL optimizer
    │   └── ProfilePage.jsx       # User stats
    └── components/
        ├── charts/ResultChart.jsx
        ├── editor/ResultsTable.jsx
        └── ui/AppShell.jsx
```


---

## Author

**Aviral Mittal**  
B.Tech Electrical Engineering, SGSITS Indore  
GitHub: [@Aviral2309](https://github.com/Aviral2309)

---

*SQLMind — Built with LangGraph · FastAPI · React · Google Gemini