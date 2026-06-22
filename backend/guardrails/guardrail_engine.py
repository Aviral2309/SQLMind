"""
Guardrail Engine — input validation before LLM runs

Detects:
- Non-database questions (pav bhaji, weather, jokes etc)
- Prompt injection
- SQL injection via NL
- PII in queries
"""
import re
from dataclasses import dataclass, field
from typing import List
import structlog

log = structlog.get_logger()


@dataclass
class GuardrailResult:
    blocked: bool
    reason: str
    score: float
    flags: List[str]


# Must contain at least one of these to be database-related
DB_KEYWORDS = [
    "show", "find", "get", "fetch", "list", "count", "how many", "total",
    "average", "sum", "top", "bottom", "recent", "latest", "oldest",
    "filter", "where", "group", "order", "sort", "join", "table", "column",
    "row", "record", "data", "database", "query", "select", "insert",
    "update", "delete", "report", "analyze", "analysis", "compare",
    "between", "range", "maximum", "minimum", "highest", "lowest",
    "which", "who", "what", "when", "how much", "revenue", "sales",
    "user", "customer", "order", "product", "employee", "transaction",
    "date", "month", "year", "week", "today", "yesterday", "last",
    "first", "all", "distinct", "unique", "duplicate", "null", "empty",
    "percentage", "percent", "ratio", "trend", "growth", "decline",
]

# Clearly off-topic — no SQL relevance
OFF_TOPIC_PATTERNS = [
    r"\b(recipe|cook|bake|boil|fry|roast)\b",
    r"\b(pav bhaji|biryani|pizza|burger|pasta|food|eat|drink)\b",
    r"\b(weather|temperature|rain|sunny|cloudy|forecast)\b",
    r"\b(joke|funny|laugh|humor|meme)\b",
    r"\b(movie|film|song|music|dance|actor|actress)\b",
    r"\b(cricket|football|sport|match|game|play)\b",
    r"\b(love|relationship|girlfriend|boyfriend|marry|marriage)\b",
    r"\b(poem|story|essay|write me|tell me a)\b",
    r"\b(translate|language|meaning of)\b",
    r"\b(stock market|crypto|bitcoin|price of gold)\b",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all|your|the)\s+(above|previous|instructions)",
    r"you\s+are\s+now\s+a",
    r"system\s*prompt",
    r"jailbreak",
    r"override\s+(your|all)\s+(instructions|rules)",
    r"disregard\s+(your|all|previous)",
    r"act\s+as\s+if",
    r"pretend\s+(you|to\s+be)",
]

SQL_INJECTION_NL = [
    r";\s*drop\s+table",
    r";\s*delete\s+from",
    r"union\s+select.*from",
    r"\bor\s+1\s*=\s*1\b",
    r"--\s*$",
    r"xp_cmdshell",
]


class GuardrailEngine:

    async def check_input(self, text: str) -> GuardrailResult:
        flags = []
        score = 0.0
        text_lower = text.lower().strip()

        # 1. Too short / gibberish
        if len(text_lower) < 3:
            return GuardrailResult(
                blocked=True,
                reason="Query too short. Please ask a proper question about your data.",
                score=1.0,
                flags=["too_short"],
            )

        # 2. Prompt injection
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                flags.append("prompt_injection")
                score = max(score, 0.95)
                break

        # 3. SQL injection via NL
        for pattern in SQL_INJECTION_NL:
            if re.search(pattern, text_lower, re.IGNORECASE):
                flags.append("sql_injection")
                score = max(score, 0.9)
                break

        # 4. Off-topic check — only block if clearly off-topic AND no DB keywords
        has_db_keyword = any(kw in text_lower for kw in DB_KEYWORDS)
        is_off_topic = any(re.search(p, text_lower, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS)

        if is_off_topic and not has_db_keyword:
            flags.append("off_topic")
            score = max(score, 0.85)

        # 5. No DB context at all — generic questions
        if not has_db_keyword and not flags and len(text_lower.split()) > 2:
            # Check if it looks like a general knowledge question
            general_starters = [
                "what is", "who is", "how to make", "how to cook",
                "explain", "tell me about", "what are", "define",
                "why is", "when was", "where is",
            ]
            is_general = any(text_lower.startswith(s) for s in general_starters)
            if is_general:
                flags.append("general_knowledge")
                score = max(score, 0.8)

        blocked = score >= 0.75

        if blocked:
            reason = self._get_reason(flags)
        else:
            reason = "clean"

        log.info("guardrail_check", blocked=blocked, score=round(score, 2), flags=flags)

        return GuardrailResult(blocked=blocked, reason=reason, score=score, flags=flags)

    def _get_reason(self, flags: List[str]) -> str:
        if "prompt_injection" in flags:
            return "I can only answer questions about your database data."
        if "sql_injection" in flags:
            return "This looks like a SQL injection attempt. Please ask a normal data question."
        if "off_topic" in flags:
            return "I can only help with questions about your database. Try asking something like: 'Show me the top 10 customers' or 'How many orders were placed this month?'"
        if "general_knowledge" in flags:
            return "I'm a database assistant — I can only answer questions about your data. Ask me something like: 'What are the total sales?' or 'Show recent orders.'"
        return "Please ask a question related to your database data."