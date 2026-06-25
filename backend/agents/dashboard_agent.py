"""
NL-to-Dashboard Agent — converts one sentence into a multi-panel BI dashboard

Flow:
1. User: "Give me a sales overview"
2. Dashboard Planner LLM → generates 4-6 widget specs (title, query, chart_type)
3. Execute all queries in parallel
4. Return structured dashboard data

This is the unique differentiator — no other Text-to-SQL tool does this.
"""
import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Optional, Any
import structlog

log = structlog.get_logger()


@dataclass
class DashboardWidget:
    title: str
    query: str
    chart_type: str  # bar | line | pie | number | table
    description: str
    columns: List[str] = field(default_factory=list)
    rows: List[list] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class Dashboard:
    title: str
    description: str
    widgets: List[DashboardWidget] = field(default_factory=list)
    generated_in_ms: float = 0.0
    error: Optional[str] = None


PLANNER_SYSTEM = """You are a BI dashboard architect. Given a user's request and database schema, 
generate 4-6 dashboard widgets that together answer the user's question comprehensively.

Return ONLY a JSON array. No explanation, no markdown. Each widget:
{
  "title": "Widget title",
  "description": "What this shows",
  "query": "SELECT ... SQL query ...",
  "chart_type": "bar|line|pie|number|table"
}

Rules:
- Include 1-2 "number" widgets for key KPIs (single value)
- Include 1-2 chart widgets for trends/comparisons  
- Include 1 table widget for detail
- Use ONLY tables/columns from the schema provided
- Add LIMIT to all queries (max 20 rows for charts, 1 for number widgets)
- chart_type "number" = single aggregated value (COUNT, SUM, AVG)
- chart_type "line" = time series data (needs date column)
- chart_type "bar" = categorical comparison
- chart_type "pie" = proportion/percentage
- chart_type "table" = detailed records"""


class DashboardAgent:
    def __init__(self, llm=None):
        self.llm = llm

    async def generate(
        self,
        user_request: str,
        schema_context: str,
        connection_string: str,
        db_type: str = "sqlite",
    ) -> Dashboard:
        import time
        start = time.time()

        if not self.llm:
            return Dashboard(
                title="Dashboard",
                description="LLM not configured",
                error="No LLM available",
            )

        # Step 1: Plan widgets
        widgets_spec = await self._plan_widgets(user_request, schema_context, db_type)
        if not widgets_spec:
            return Dashboard(
                title=user_request,
                description="Could not generate dashboard plan",
                error="Planning failed",
            )

        # Step 2: Execute all queries in parallel
        from agents.executor import QueryExecutor
        executor = QueryExecutor(connection_string)

        tasks = [
            self._execute_widget(executor, spec)
            for spec in widgets_spec
        ]
        widgets = await asyncio.gather(*tasks, return_exceptions=True)

        valid_widgets = []
        for w in widgets:
            if isinstance(w, Exception):
                continue
            if w:
                valid_widgets.append(w)

        elapsed = (time.time() - start) * 1000

        # Generate dashboard title from request
        title = await self._generate_title(user_request)

        return Dashboard(
            title=title,
            description=f"Generated from: \"{user_request}\"",
            widgets=valid_widgets,
            generated_in_ms=round(elapsed, 1),
        )

    async def _plan_widgets(self, request: str, schema: str, db_type: str) -> list:
        from langchain_core.messages import HumanMessage, SystemMessage

        dialect_hint = {
            "mysql": "Use MySQL syntax with backticks for names with spaces.",
            "postgres": "Use PostgreSQL syntax with double quotes for names with spaces.",
            "sqlite": "Use SQLite syntax with double quotes for names with spaces.",
        }.get(db_type, "")

        prompt = f"""User request: {request}

Database schema:
{schema}

{dialect_hint}

Generate 4-5 dashboard widgets as a JSON array."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=PLANNER_SYSTEM),
                HumanMessage(content=prompt),
            ])

            content = response.content.strip()
            # Strip markdown if present
            if "```" in content:
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            widgets = json.loads(content)
            if isinstance(widgets, list):
                return widgets[:6]
            return []

        except Exception as e:
            log.error("dashboard_plan_failed", error=str(e))
            return []

    async def _execute_widget(self, executor, spec: dict) -> Optional[DashboardWidget]:
        import time
        start = time.time()

        title = spec.get("title", "Widget")
        query = spec.get("query", "")
        chart_type = spec.get("chart_type", "table")
        description = spec.get("description", "")

        if not query:
            return None

        try:
            result = executor.execute(query)
            elapsed = (time.time() - start) * 1000

            if not result.success:
                return DashboardWidget(
                    title=title, query=query,
                    chart_type=chart_type, description=description,
                    error=result.error,
                )

            return DashboardWidget(
                title=title, query=query,
                chart_type=chart_type, description=description,
                columns=result.columns,
                rows=result.rows,
                execution_time_ms=round(elapsed, 1),
            )
        except Exception as e:
            return DashboardWidget(
                title=title, query=query,
                chart_type=chart_type, description=description,
                error=str(e),
            )

    async def _generate_title(self, request: str) -> str:
        words = request.strip().title()
        if len(words) > 50:
            words = words[:47] + "..."
        return words
