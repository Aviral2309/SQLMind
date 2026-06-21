"""
Answer Agent — converts SQL execution results into natural language answers

Flow: NL question + SQL results → plain English answer
This enables "Data Q&A mode" — user asks question, gets direct answer
"""
from langchain_core.messages import HumanMessage, SystemMessage
import structlog

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a data analyst assistant. 
Given a user's question and the database query results, provide a clear, direct answer.

Rules:
- Answer directly — lead with the key fact
- Use numbers from the data exactly
- 1-3 sentences maximum
- If data is empty, say "No data found for this query"
- Never say "based on the query results" — just answer naturally
- Format numbers nicely (use commas for thousands)
"""


class AnswerAgent:
    def __init__(self, llm):
        self.llm = llm

    async def answer(
        self,
        question: str,
        columns: list,
        rows: list,
        sql: str,
    ) -> str:
        if not rows:
            return "No data found for this query."

        # Format results as readable table text
        result_text = self._format_results(columns, rows)

        prompt = f"""Question: {question}

Query results:
{result_text}

Answer the question directly using this data."""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            log.warning("answer_agent_failed", error=str(e))
            # Fallback: return first row as text
            if rows:
                return f"{', '.join(str(v) for v in rows[0])}"
            return "Could not generate answer."

    def _format_results(self, columns: list, rows: list) -> str:
        if not columns or not rows:
            return "No results"

        # Header
        lines = [" | ".join(str(c) for c in columns)]
        lines.append("-" * len(lines[0]))

        # Rows (max 10 for context)
        for row in rows[:10]:
            lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))

        if len(rows) > 10:
            lines.append(f"... and {len(rows) - 10} more rows")

        return "\n".join(lines)
