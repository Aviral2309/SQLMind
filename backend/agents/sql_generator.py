"""
SQL Generator Agent — NL to SQL with dialect-aware generation
"""
from dataclasses import dataclass
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
import structlog

log = structlog.get_logger()


@dataclass
class SQLGenerationResult:
    sql: str
    tokens_used: int
    confidence: float = 0.85


SYSTEM_PROMPT = """You are an expert SQL query generator. Convert natural language to precise SQL.

CRITICAL RULES:
1. Output ONLY the SQL query — no explanation, no markdown, no backticks around the whole query
2. Use ONLY tables and columns that exist in the provided schema
3. For MySQL: use backticks for column/table names with spaces: `column name`
4. For PostgreSQL: use double quotes for names with spaces: "column name"  
5. For SQLite: use double quotes for names with spaces: "column name"
6. Always add LIMIT (default 100) unless aggregating
7. Never generate DROP, DELETE without WHERE, TRUNCATE, ALTER TABLE
8. If column has spaces, ALWAYS quote it with the right syntax for the dialect

DIALECT RULES:
- mysql: backticks `name`, string concat with CONCAT(), LIMIT at end
- postgres: double quotes "name", string concat with ||, LIMIT at end  
- sqlite: double quotes "name", LIMIT at end

If previous attempt failed, fix the specific error mentioned."""


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

        error_ctx = ""
        if previous_errors:
            error_ctx = f"\nPrevious attempt FAILED with these errors — fix them:\n" + \
                       "\n".join(f"- {e}" for e in previous_errors) + "\n"

        # Dialect-specific instructions
        dialect_hint = {
            "mysql": "Use MySQL syntax. Quote column/table names with SPACES using BACKTICKS like `column name`.",
            "postgres": 'Use PostgreSQL syntax. Quote column/table names with SPACES using DOUBLE QUOTES like "column name".',
            "sqlite": 'Use SQLite syntax. Quote column/table names with SPACES using DOUBLE QUOTES like "column name".',
        }.get(db_type, "Use standard SQL.")

        user_prompt = f"""Database type: {db_type}
{dialect_hint}

Schema:
{schema_context}
{error_ctx}
Question: {natural_language}

Write the SQL query:"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        raw_sql = response.content.strip()
        sql = self._clean_sql(raw_sql, db_type)

        tokens_used = 0
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                tokens_used = response.usage_metadata.get("total_tokens", 0) or 0
        except Exception:
            pass

        return SQLGenerationResult(sql=sql, tokens_used=tokens_used)

    def _clean_sql(self, raw: str, db_type: str) -> str:
        # Remove markdown code blocks
        if "```" in raw:
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Remove leading/trailing whitespace
        sql = raw.strip()

        # Fix common dialect mistakes
        if db_type == "mysql":
            # Replace double quotes with backticks for identifiers in MySQL
            # But be careful — only replace quoted identifiers, not string values
            import re
            # Replace "identifier" with `identifier` only when not in WHERE string context
            sql = re.sub(r'(?<![=<>!\s])"([^"]+)"(?!\s*[,)]?\s*(?:FROM|WHERE|AND|OR|LIMIT|GROUP|ORDER|JOIN|ON|AS))',
                        lambda m: f'`{m.group(1)}`', sql)

        return sql