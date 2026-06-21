"""
Explainer Agent — generates plain English explanation of generated SQL
"""
from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are a helpful data analyst. Explain SQL queries in simple, clear English.

Rules:
- 2-4 sentences maximum
- No technical jargon — explain what the query DOES, not how SQL works
- Mention which tables are involved
- Mention any filters, grouping, or sorting in plain English
- Start with "This query..."
"""

class ExplainerAgent:
    def __init__(self, llm):
        self.llm = llm

    async def explain(self, sql: str, natural_language: str, schema_context: str) -> str:
        prompt = f"""Original question: {natural_language}

Generated SQL:
{sql}

Explain what this SQL query does in 2-4 plain English sentences."""

        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        try:
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            return f"This query retrieves data based on: {natural_language}"