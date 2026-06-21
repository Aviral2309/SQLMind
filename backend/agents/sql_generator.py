"""
SQL Generator Agent — NL → SQL with schema-aware prompting
"""
from dataclasses import dataclass
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
import structlog
import sqlglot

log = structlog.get_logger()


@dataclass
class SQLGenerationResult:
    sql: str
    tokens_used: int
    confidence: float
    reasoning: str


SYSTEM_PROMPT = """You are an expert SQL query generator. Your job is to convert natural language questions into precise, optimized SQL queries.

Rules:
1. Generate ONLY the SQL query — no explanation, no markdown, no backticks
2. Use only tables and columns that exist in the provided schema
3. Always add appropriate LIMIT clauses (default LIMIT 1000 unless aggregating)
4. Use table aliases for readability
5. Prefer CTEs over deeply nested subqueries for readability
6. Never generate DROP, DELETE without WHERE, TRUNCATE, or ALTER TABLE
7. For ambiguous requests, choose the most conservative interpretation
8. Add comments in SQL for complex logic using -- notation

If you receive previous errors, fix them specifically."""

FEW_SHOT_EXAMPLES = [
    {
        "nl": "Show me top 10 customers by total order value",
        "sql": """SELECT 
    c.customer_id,
    c.name,
    SUM(o.total_amount) AS total_order_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_order_value DESC
LIMIT 10;"""
    },
    {
        "nl": "Find customers who haven't placed any orders in the last 90 days",
        "sql": """SELECT 
    c.customer_id,
    c.name,
    c.email,
    MAX(o.created_at) AS last_order_date
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.email
HAVING MAX(o.created_at) < NOW() - INTERVAL '90 days'
    OR MAX(o.created_at) IS NULL
ORDER BY last_order_date NULLS FIRST
LIMIT 1000;"""
    },
]


class SQLGeneratorAgent:
    def __init__(self, llm):
        self.llm = llm

    async def generate(
        self,
        natural_language: str,
        schema_context: str,
        db_type: str,
        previous_errors: List[str] = None,
        rag_chunks: List[dict] = None,
    ) -> SQLGenerationResult:

        few_shot_text = self._format_few_shots(rag_chunks or [])
        error_context = self._format_errors(previous_errors or [])

        user_prompt = f"""Database type: {db_type}

Schema:
{schema_context}

{few_shot_text}
{error_context}

Question: {natural_language}

Generate the SQL query:"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        raw_sql = response.content.strip()

        # Strip markdown code blocks if LLM included them
        sql = self._clean_sql(raw_sql)

        # Normalize with sqlglot
        try:
            parsed = sqlglot.parse_one(sql, dialect=db_type)
            sql = parsed.sql(dialect=db_type, pretty=True)
        except Exception:
            pass  # Use raw if parse fails — verifier will catch

        tokens_used = response.usage_metadata.get("total_tokens", 0) if hasattr(response, "usage_metadata") else 0

        return SQLGenerationResult(
            sql=sql,
            tokens_used=tokens_used,
            confidence=0.85,
            reasoning="Generated from schema context and NL query",
        )

    def _clean_sql(self, raw: str) -> str:
        """Remove markdown fences if LLM included them"""
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            return "\n".join(lines).strip()
        return raw

    def _format_few_shots(self, rag_chunks: List[dict]) -> str:
        if not rag_chunks:
            return ""
        examples = "\nSimilar query examples:\n"
        for chunk in rag_chunks[:3]:
            if chunk.get("nl") and chunk.get("sql"):
                examples += f"Q: {chunk['nl']}\nSQL: {chunk['sql']}\n\n"
        return examples

    def _format_errors(self, errors: List[str]) -> str:
        if not errors:
            return ""
        return f"\nPrevious attempt failed with these errors — fix them:\n" + \
               "\n".join(f"- {e}" for e in errors) + "\n"
