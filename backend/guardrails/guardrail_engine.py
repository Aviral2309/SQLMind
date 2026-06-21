"""
Guardrail Engine — LLM input/output safety layer

Detects:
- Prompt injection attempts ("ignore previous instructions")
- PII in user queries (Presidio-based)
- Jailbreak patterns
- Malicious SQL injection via NL
- Off-topic requests (not database-related)
"""
import re
from dataclasses import dataclass
from typing import List, Optional
import structlog

log = structlog.get_logger()


@dataclass
class GuardrailResult:
    blocked: bool
    reason: str
    score: float  # 0.0 = safe, 1.0 = definitely malicious
    flags: List[str]


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all|your|the)\s+(above|previous|instructions)",
    r"you\s+are\s+now\s+a?n?\s+\w+",  # "you are now a DAN"
    r"system\s*prompt",
    r"jailbreak",
    r"act\s+as\s+if",
    r"pretend\s+(you|to\s+be)",
    r"override\s+(your|all)\s+(instructions|rules|guidelines)",
    r"disregard\s+(your|all|previous)",
]

SQL_INJECTION_VIA_NL = [
    r";\s*drop\s+table",
    r";\s*delete\s+from",
    r"union\s+select",
    r"1\s*=\s*1",
    r"or\s+true",
    r"--\s*$",
]

OFF_TOPIC_PATTERNS = [
    r"\b(write\s+me\s+a\s+(poem|story|essay))\b",
    r"\b(what\s+is\s+the\s+weather)\b",
    r"\b(tell\s+me\s+a\s+joke)\b",
    r"\b(translate\s+this\s+to)\b",
]

# Harmless SQL-related patterns to explicitly allow
SQL_RELATED_KEYWORDS = [
    "select", "find", "show", "list", "count", "average", "total",
    "top", "bottom", "recent", "filter", "group", "join", "table",
    "column", "row", "query", "database", "where", "order",
]


class GuardrailEngine:
    def __init__(self):
        self._pii_analyzer = None  # Lazy load Presidio

    async def check_input(self, text: str) -> GuardrailResult:
        """Full input guardrail check"""
        flags = []
        score = 0.0

        text_lower = text.lower()

        # 1. Prompt injection
        injection_score, injection_flags = self._check_injection(text_lower)
        flags.extend(injection_flags)
        score = max(score, injection_score)

        # 2. SQL injection via NL
        sqli_score, sqli_flags = self._check_sql_injection_nl(text_lower)
        flags.extend(sqli_flags)
        score = max(score, sqli_score)

        # 3. Off-topic check
        if self._is_off_topic(text_lower):
            flags.append("off_topic")
            score = max(score, 0.7)

        # 4. Length check
        if len(text) > 2000:
            flags.append("excessive_length")
            score = max(score, 0.3)

        # 5. PII detection (async, only if enabled)
        try:
            pii_flags = await self._check_pii(text)
            flags.extend(pii_flags)
            if pii_flags:
                score = max(score, 0.4)
        except Exception:
            pass  # Don't block if PII check fails

        blocked = score >= 0.7
        reason = ", ".join(flags) if flags else "clean"

        log.info("guardrail_check", blocked=blocked, score=score, flags=flags)

        return GuardrailResult(
            blocked=blocked,
            reason=reason,
            score=score,
            flags=flags,
        )

    def _check_injection(self, text: str):
        flags = []
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                flags.append(f"injection_pattern:{pattern[:30]}")
        score = min(len(flags) * 0.4, 1.0)
        return score, flags

    def _check_sql_injection_nl(self, text: str):
        flags = []
        for pattern in SQL_INJECTION_VIA_NL:
            if re.search(pattern, text, re.IGNORECASE):
                flags.append(f"sql_injection_nl:{pattern[:30]}")
        score = min(len(flags) * 0.5, 1.0)
        return score, flags

    def _is_off_topic(self, text: str) -> bool:
        """Check if query is clearly not database-related"""
        has_sql_keyword = any(kw in text for kw in SQL_RELATED_KEYWORDS)
        has_off_topic = any(
            re.search(p, text, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS
        )
        return has_off_topic and not has_sql_keyword

    async def _check_pii(self, text: str) -> List[str]:
        """Presidio-based PII detection"""
        try:
            from presidio_analyzer import AnalyzerEngine
            if self._pii_analyzer is None:
                self._pii_analyzer = AnalyzerEngine()

            results = self._pii_analyzer.analyze(text=text, language="en")
            pii_types = [r.entity_type for r in results if r.score > 0.7]
            return [f"pii:{t}" for t in pii_types]
        except ImportError:
            return []
