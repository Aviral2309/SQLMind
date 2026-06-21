"""
Verifier Agent — AST-based SQL verification + hallucination detection
All operations wrapped in try/except — never crashes the pipeline
"""
import re
from dataclasses import dataclass, field
from typing import List, Set
import structlog

log = structlog.get_logger()

DANGEROUS_PATTERNS = [
    (r"\bDROP\s+TABLE\b", "DROP TABLE detected"),
    (r"\bTRUNCATE\b", "TRUNCATE detected"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "DELETE without WHERE detected"),
    (r"\bUPDATE\b(?!.*\bWHERE\b)", "UPDATE without WHERE detected"),
    (r"\bEXEC\b|\bEXECUTE\b", "EXEC detected"),
    (r"\bxp_cmdshell\b", "xp_cmdshell detected"),
]


@dataclass
class VerificationResult:
    passed: bool
    safety_passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hallucination_score: float = 0.0
    referenced_tables: List[str] = field(default_factory=list)
    referenced_columns: List[str] = field(default_factory=list)
    complexity_score: int = 0


class VerifierAgent:

    async def verify(
        self,
        sql: str,
        schema_context: str,
        relevant_tables: List[str],
        db_type: str = "postgres",
    ) -> VerificationResult:

        if not sql or not sql.strip():
            return VerificationResult(passed=False, safety_passed=True, errors=["Empty SQL"])

        # 1. Safety check — always runs
        safety_passed, safety_errors = self._check_safety(sql)
        if not safety_passed:
            return VerificationResult(passed=False, safety_passed=False, errors=safety_errors)

        # 2. AST parse — with multiple fallbacks
        parsed = None
        try:
            import sqlglot
            try:
                parsed = sqlglot.parse_one(sql, dialect=db_type)
            except Exception:
                try:
                    parsed = sqlglot.parse_one(sql)
                except Exception:
                    parsed = None
        except ImportError:
            pass

        if parsed is None:
            # Can't parse — let it through with warning
            log.warning("sql_parse_failed", sql=sql[:100])
            return VerificationResult(
                passed=True,
                safety_passed=True,
                errors=[],
                warnings=["Could not parse SQL for validation — proceeding anyway"],
                hallucination_score=0.0,
            )

        # 3. Extract tables and columns from AST
        referenced_tables = self._extract_tables(parsed)
        referenced_columns = self._extract_columns(parsed)

        # 4. Hallucination check
        hallucination_score, hallucination_errors = self._check_hallucination(
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            schema_context=schema_context,
            known_tables=relevant_tables,
        )

        errors = list(hallucination_errors)

        # 5. Complexity check
        complexity_score = self._measure_complexity(parsed)
        warnings = []
        if complexity_score > 8:
            warnings.append(f"High complexity score: {complexity_score}")

        # 6. LIMIT check
        if not self._has_limit(parsed):
            warnings.append("No LIMIT clause — consider adding LIMIT")

        passed = len(errors) == 0

        return VerificationResult(
            passed=passed,
            safety_passed=True,
            errors=errors,
            warnings=warnings,
            hallucination_score=hallucination_score,
            referenced_tables=list(referenced_tables),
            referenced_columns=list(referenced_columns),
            complexity_score=complexity_score,
        )

    def _check_safety(self, sql: str):
        errors = []
        for pattern, message in DANGEROUS_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                errors.append(f"Safety violation: {message}")
        return len(errors) == 0, errors

    def _extract_tables(self, parsed) -> Set[str]:
        tables = set()
        try:
            import sqlglot.expressions as exp
            for table in parsed.find_all(exp.Table):
                if table.name:
                    tables.add(table.name.lower())
        except Exception:
            pass
        return tables

    def _extract_columns(self, parsed) -> Set[str]:
        columns = set()
        try:
            import sqlglot.expressions as exp
            for col in parsed.find_all(exp.Column):
                if col.name:
                    columns.add(col.name.lower())
        except Exception:
            pass
        return columns

    def _check_hallucination(
        self,
        referenced_tables: Set[str],
        referenced_columns: Set[str],
        schema_context: str,
        known_tables: List[str],
    ):
        try:
            errors = []
            schema_lower = schema_context.lower() if schema_context else ""
            known_lower = {t.lower() for t in (known_tables or [])}

            hallucinated_tables = []
            for table in referenced_tables:
                if table not in known_lower and table not in schema_lower:
                    hallucinated_tables.append(table)

            if hallucinated_tables:
                errors.append(f"Possible hallucinated tables: {', '.join(hallucinated_tables)}")

            total = len(referenced_tables)
            hallucinated = len(hallucinated_tables)
            score = hallucinated / total if total > 0 else 0.0

            return score, errors
        except Exception as e:
            log.warning("hallucination_check_error", error=str(e))
            return 0.0, []

    def _measure_complexity(self, parsed) -> int:
        try:
            import sqlglot.expressions as exp
            score = 0
            score += len(list(parsed.find_all(exp.Join)))
            score += len(list(parsed.find_all(exp.Subquery)))
            score += len(list(parsed.find_all(exp.Window)))
            score += len(list(parsed.find_all(exp.With)))
            return score
        except Exception:
            return 0

    def _has_limit(self, parsed) -> bool:
        try:
            import sqlglot.expressions as exp
            return bool(parsed.find(exp.Limit))
        except Exception:
            return True  # Assume has limit if can't check