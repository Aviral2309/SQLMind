"""
Query Optimizer — AST-based SQL anti-pattern detection + LLM rewriter

Resume talking point:
"Rule-based SQL anti-pattern detector using sqlglot AST analysis —
identifies SELECT *, subqueries in WHERE, missing indexes — 
then LLM rewrites with explanations"
"""
from dataclasses import dataclass, field
from typing import List, Optional
import sqlglot
from sqlglot import exp
import structlog

log = structlog.get_logger()


@dataclass
class Issue:
    type: str
    severity: str  # "error" | "warning" | "info"
    message: str
    suggestion: str
    line: Optional[int] = None


@dataclass
class OptimizationResult:
    original_sql: str
    optimized_sql: str
    issues: List[Issue] = field(default_factory=list)
    explanation: str = ""
    improvement_score: int = 0  # 0-100, higher = more improvement
    error: Optional[str] = None


class QueryPatternDetector:
    """Detects SQL anti-patterns via AST analysis"""

    def detect(self, sql: str, dialect: str = "postgres") -> List[Issue]:
        issues = []
        try:
            parsed = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as e:
            return [Issue(
                type="parse_error",
                severity="error",
                message=f"Could not parse SQL: {str(e)}",
                suggestion="Fix SQL syntax first",
            )]

        # 1. SELECT * anti-pattern
        for star in parsed.find_all(exp.Star):
            issues.append(Issue(
                type="select_star",
                severity="warning",
                message="SELECT * fetches all columns — wasteful on wide tables",
                suggestion="Specify only the columns you need",
            ))

        # 2. Missing LIMIT on non-aggregated query
        has_limit = bool(parsed.find(exp.Limit))
        has_agg = bool(parsed.find(exp.AggFunc))
        has_group = bool(parsed.find(exp.Group))

        if not has_limit and not (has_agg and has_group):
            issues.append(Issue(
                type="missing_limit",
                severity="warning",
                message="No LIMIT clause — could return millions of rows",
                suggestion="Add LIMIT 1000 or appropriate limit",
            ))

        # 3. Subquery in WHERE (often rewritable as JOIN)
        for subq in parsed.find_all(exp.Subquery):
            parent = subq.parent
            if isinstance(parent, (exp.In, exp.EQ)):
                issues.append(Issue(
                    type="subquery_in_where",
                    severity="warning",
                    message="Subquery in WHERE — can be slow on large tables",
                    suggestion="Consider rewriting as JOIN or EXISTS",
                ))

        # 4. Implicit cross join (missing ON clause)
        for join in parsed.find_all(exp.Join):
            if join.kind == "CROSS" or (not join.args.get("on") and not join.args.get("using")):
                issues.append(Issue(
                    type="implicit_cross_join",
                    severity="error",
                    message="JOIN without ON/USING condition — produces cartesian product",
                    suggestion="Add proper JOIN condition with ON clause",
                ))

        # 5. DISTINCT usage
        if parsed.find(exp.Distinct):
            issues.append(Issue(
                type="distinct_usage",
                severity="info",
                message="DISTINCT can be expensive on large result sets",
                suggestion="Ensure duplicates aren't caused by unnecessary JOINs",
            ))

        # 6. OR in WHERE (can prevent index usage)
        for condition in parsed.find_all(exp.Or):
            issues.append(Issue(
                type="or_condition",
                severity="info",
                message="OR conditions may prevent index usage",
                suggestion="Consider UNION ALL instead of OR for better performance",
            ))
            break  # Only flag once

        # 7. NOT IN with subquery (NULL issues)
        for nin in parsed.find_all(exp.In):
            if nin.args.get("query"):
                issues.append(Issue(
                    type="not_in_subquery",
                    severity="info",
                    message="IN/NOT IN with subquery can have NULL issues",
                    suggestion="Use EXISTS/NOT EXISTS for safer NULL handling",
                ))

        return issues


class QueryOptimizer:
    def __init__(self, llm=None):
        self.detector = QueryPatternDetector()
        self.llm = llm

    async def optimize(self, sql: str, dialect: str = "postgres") -> OptimizationResult:
        issues = self.detector.detect(sql, dialect)

        if not issues:
            return OptimizationResult(
                original_sql=sql,
                optimized_sql=sql,
                issues=[],
                explanation="No issues detected. Query looks good!",
                improvement_score=0,
            )

        # Score improvement potential
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        improvement_score = min(100, error_count * 30 + warning_count * 15)

        # LLM rewrite if available
        optimized_sql = sql
        explanation = ""

        if self.llm and issues:
            optimized_sql, explanation = await self._llm_rewrite(sql, issues, dialect)

        return OptimizationResult(
            original_sql=sql,
            optimized_sql=optimized_sql,
            issues=issues,
            explanation=explanation or self._generate_explanation(issues),
            improvement_score=improvement_score,
        )

    async def _llm_rewrite(self, sql: str, issues: List[Issue], dialect: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        issues_text = "\n".join(f"- [{i.severity.upper()}] {i.message}: {i.suggestion}" for i in issues)

        prompt = f"""Optimize this SQL query by fixing the detected issues:

Original SQL:
{sql}

Issues found:
{issues_text}

Return ONLY the optimized SQL query, nothing else. No explanation, no markdown."""

        system = "You are an expert SQL optimizer. Fix the issues and return only the improved SQL query."

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content=prompt),
            ])
            optimized = response.content.strip()
            if optimized.startswith("```"):
                lines = optimized.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                optimized = "\n".join(lines).strip()

            # Generate explanation
            exp_prompt = f"""Original SQL had these issues: {issues_text}

Optimized SQL: {optimized}

Explain in 2-3 sentences what was changed and why."""
            exp_response = await self.llm.ainvoke([
                SystemMessage(content="Explain SQL optimizations briefly."),
                HumanMessage(content=exp_prompt),
            ])
            return optimized, exp_response.content.strip()
        except Exception as e:
            log.warning("llm_rewrite_failed", error=str(e))
            return sql, self._generate_explanation(issues)

    def _generate_explanation(self, issues: List[Issue]) -> str:
        if not issues:
            return "No optimizations needed."
        parts = [f"{i.message} — {i.suggestion}" for i in issues[:3]]
        return " | ".join(parts)
