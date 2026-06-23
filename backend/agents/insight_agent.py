"""
Auto-Insight Agent — analyzes a database and generates automatic insights

Flow:
1. Introspect all tables
2. Run 5 parallel diagnostic queries
3. Feed results to LLM
4. Return structured insight cards

Demo moment: "Analyze my data" → instant business intelligence
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Any
import structlog

log = structlog.get_logger()


@dataclass
class InsightCard:
    type: str          # "summary" | "anomaly" | "trend" | "top_values" | "quality"
    title: str
    value: str         # main metric/finding
    detail: str        # explanation
    severity: str = "info"  # "info" | "warning" | "critical"
    data: Optional[Any] = None  # chart data if applicable


@dataclass
class InsightReport:
    connection_name: str
    total_tables: int
    total_rows: int
    insights: List[InsightCard] = field(default_factory=list)
    summary: str = ""
    generated_in_ms: float = 0.0
    error: Optional[str] = None


class AutoInsightAgent:
    """
    Runs parallel diagnostic queries on a database and generates
    AI-powered insights without user asking specific questions.
    """

    def __init__(self, llm=None):
        self.llm = llm

    async def analyze(
        self,
        connection_string: str,
        connection_name: str,
        db_type: str = "sqlite",
    ) -> InsightReport:
        import time
        start = time.time()

        from agents.executor import QueryExecutor
        from agents.schema_agent import DBInspector, SchemaFormatter

        # Step 1: Introspect
        inspector = DBInspector(connection_string)
        ok, error = inspector.connect()
        if not ok:
            return InsightReport(
                connection_name=connection_name,
                total_tables=0, total_rows=0,
                error=f"Could not connect: {error}"
            )

        try:
            tables = inspector.get_all_tables()
        finally:
            inspector.close()

        if not tables:
            return InsightReport(
                connection_name=connection_name,
                total_tables=0, total_rows=0,
                error="No tables found"
            )

        executor = QueryExecutor(connection_string)
        insights = []
        total_rows = 0

        # Step 2: Run parallel diagnostic queries
        tasks = []
        for table in tables[:8]:  # max 8 tables
            tasks.append(self._analyze_table(executor, table, db_type))

        table_results = await asyncio.gather(*tasks, return_exceptions=True)

        for table, result in zip(tables[:8], table_results):
            if isinstance(result, Exception):
                continue
            if result:
                insights.extend(result.get("insights", []))
                total_rows += result.get("row_count", 0)

        # Step 3: LLM summary
        summary = await self._generate_summary(
            tables=tables,
            insights=insights,
            connection_name=connection_name,
            total_rows=total_rows,
        )

        elapsed = (time.time() - start) * 1000

        return InsightReport(
            connection_name=connection_name,
            total_tables=len(tables),
            total_rows=total_rows,
            insights=insights[:15],  # cap at 15
            summary=summary,
            generated_in_ms=round(elapsed, 1),
        )

    async def _analyze_table(self, executor, table, db_type: str) -> dict:
        """Run diagnostic queries on a single table"""
        name = table.name
        insights = []
        row_count = 0

        # Quote table name based on dialect
        q = f'`{name}`' if db_type == 'mysql' else f'"{name}"'

        # 1. Row count
        try:
            r = executor.execute(f"SELECT COUNT(*) as cnt FROM {q}")
            if r.success and r.rows:
                row_count = int(r.rows[0][0] or 0)
                insights.append(InsightCard(
                    type="summary",
                    title=f"{name}",
                    value=f"{row_count:,} rows",
                    detail=f"Table has {row_count:,} records with {len(table.columns)} columns",
                ))
        except Exception:
            pass

        if row_count == 0:
            return {"insights": insights, "row_count": 0}

        # 2. Null analysis on first 5 columns
        null_insights = await self._check_nulls(executor, name, table.columns[:5], row_count, db_type)
        insights.extend(null_insights)

        # 3. Top values for categorical columns
        top_insights = await self._top_values(executor, name, table, db_type)
        insights.extend(top_insights)

        # 4. Date/time trend if date column exists
        trend_insight = await self._time_trend(executor, name, table, db_type)
        if trend_insight:
            insights.append(trend_insight)

        # 5. Numeric stats for numeric columns
        stat_insights = await self._numeric_stats(executor, name, table, db_type)
        insights.extend(stat_insights)

        return {"insights": insights, "row_count": row_count}

    async def _check_nulls(self, executor, table_name, columns, row_count, db_type):
        insights = []
        q = f'`{table_name}`' if db_type == 'mysql' else f'"{table_name}"'
        for col in columns:
            try:
                cq = f'`{col["name"]}`' if db_type == 'mysql' else f'"{col["name"]}"'
                r = executor.execute(f"SELECT COUNT(*) FROM {q} WHERE {cq} IS NULL")
                if r.success and r.rows:
                    null_count = int(r.rows[0][0] or 0)
                    null_pct = (null_count / row_count * 100) if row_count > 0 else 0
                    if null_pct > 20:
                        insights.append(InsightCard(
                            type="quality",
                            title=f"High nulls: {table_name}.{col['name']}",
                            value=f"{null_pct:.1f}% null",
                            detail=f"{null_count:,} of {row_count:,} rows have no value",
                            severity="warning" if null_pct > 50 else "info",
                        ))
            except Exception:
                pass
        return insights

    async def _top_values(self, executor, table_name, table, db_type):
        insights = []
        q = f'`{table_name}`' if db_type == 'mysql' else f'"{table_name}"'

        # Find first text column that's not ID
        text_col = None
        for col in table.columns:
            if col["name"] in table.primary_keys:
                continue
            if any(t in col["type"].upper() for t in ["CHAR", "TEXT", "VARCHAR"]):
                text_col = col["name"]
                break

        if not text_col:
            return insights

        try:
            cq = f'`{text_col}`' if db_type == 'mysql' else f'"{text_col}"'
            r = executor.execute(
                f"SELECT {cq}, COUNT(*) as cnt FROM {q} "
                f"GROUP BY {cq} ORDER BY cnt DESC LIMIT 5"
            )
            if r.success and r.rows and len(r.rows) > 1:
                top = r.rows[0]
                top_val = str(top[0]) if top[0] else "NULL"
                top_cnt = int(top[1] or 0)
                all_cnt = sum(int(row[1] or 0) for row in r.rows)
                pct = (top_cnt / all_cnt * 100) if all_cnt > 0 else 0

                insights.append(InsightCard(
                    type="top_values",
                    title=f"Top {text_col} in {table_name}",
                    value=f'"{top_val}" ({pct:.1f}%)',
                    detail=f"Top 5 values: {', '.join(str(row[0]) for row in r.rows[:5] if row[0])}",
                    data={
                        "labels": [str(row[0]) for row in r.rows],
                        "values": [int(row[1] or 0) for row in r.rows],
                    }
                ))
        except Exception:
            pass
        return insights

    async def _time_trend(self, executor, table_name, table, db_type):
        q = f'`{table_name}`' if db_type == 'mysql' else f'"{table_name}"'
        date_keywords = ["date", "time", "created", "updated", "at", "on", "day"]

        date_col = None
        for col in table.columns:
            if any(kw in col["name"].lower() for kw in date_keywords):
                date_col = col["name"]
                break

        if not date_col:
            return None

        try:
            cq = f'`{date_col}`' if db_type == 'mysql' else f'"{date_col}"'
            if db_type == "mysql":
                trunc = f"DATE({cq})"
            elif db_type == "sqlite":
                trunc = f"DATE({cq})"
            else:
                trunc = f"DATE({cq})"

            r = executor.execute(
                f"SELECT {trunc} as day, COUNT(*) as cnt FROM {q} "
                f"WHERE {cq} IS NOT NULL "
                f"GROUP BY day ORDER BY day DESC LIMIT 30"
            )
            if r.success and r.rows and len(r.rows) >= 3:
                recent = [int(row[1] or 0) for row in r.rows[:7]]
                older = [int(row[1] or 0) for row in r.rows[7:14]]
                avg_recent = sum(recent) / len(recent) if recent else 0
                avg_older = sum(older) / len(older) if older else 1

                change = ((avg_recent - avg_older) / avg_older * 100) if avg_older else 0
                trend = "up" if change > 5 else "down" if change < -5 else "stable"

                return InsightCard(
                    type="trend",
                    title=f"Trend: {table_name} by {date_col}",
                    value=f"{trend.upper()} {abs(change):.1f}% vs prior week",
                    detail=f"Avg {avg_recent:.0f}/day recently vs {avg_older:.0f}/day prior",
                    severity="warning" if change < -20 else "info",
                    data={
                        "labels": [str(row[0]) for row in reversed(r.rows)],
                        "values": [int(row[1] or 0) for row in reversed(r.rows)],
                    }
                )
        except Exception:
            pass
        return None

    async def _numeric_stats(self, executor, table_name, table, db_type):
        insights = []
        q = f'`{table_name}`' if db_type == 'mysql' else f'"{table_name}"'

        numeric_cols = [
            col for col in table.columns
            if any(t in col["type"].upper() for t in ["INT", "FLOAT", "REAL", "NUMERIC", "DECIMAL", "DOUBLE"])
            and col["name"] not in table.primary_keys
        ][:2]  # max 2 numeric columns

        for col in numeric_cols:
            try:
                cq = f'`{col["name"]}`' if db_type == 'mysql' else f'"{col["name"]}"'
                r = executor.execute(
                    f"SELECT MIN({cq}), MAX({cq}), AVG({cq}), COUNT({cq}) FROM {q} WHERE {cq} IS NOT NULL"
                )
                if r.success and r.rows and r.rows[0][0] is not None:
                    mn, mx, avg, cnt = r.rows[0]
                    insights.append(InsightCard(
                        type="summary",
                        title=f"{table_name}.{col['name']} stats",
                        value=f"Avg: {float(avg or 0):.2f}",
                        detail=f"Min: {mn} · Max: {mx} · Count: {cnt:,}",
                    ))
            except Exception:
                pass
        return insights

    async def _generate_summary(self, tables, insights, connection_name, total_rows) -> str:
        if not self.llm:
            return f"Database '{connection_name}' has {len(tables)} tables with {total_rows:,} total rows."

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            insight_text = "\n".join(
                f"- {i.title}: {i.value} — {i.detail}"
                for i in insights[:8]
            )

            response = await self.llm.ainvoke([
                SystemMessage(content="You are a data analyst. Give a concise 2-3 sentence business summary of this database analysis. Be specific about numbers. No fluff."),
                HumanMessage(content=f"""
Database: {connection_name}
Tables: {len(tables)} ({', '.join(t.name for t in tables[:5])})
Total rows: {total_rows:,}

Key findings:
{insight_text}

Write a 2-3 sentence executive summary.""")
            ])
            return response.content.strip()
        except Exception as e:
            log.warning("insight_summary_failed", error=str(e))
            return f"Database has {len(tables)} tables with {total_rows:,} total rows across {len(insights)} findings."
