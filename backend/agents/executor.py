"""
Query Executor — runs generated SQL on target database
Returns results, column names, row count, execution time
"""
import time
import json
from typing import List, Optional, Any
from dataclasses import dataclass, field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import structlog

log = structlog.get_logger()


@dataclass
class ExecutionResult:
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    truncated: bool = False  # True if results were limited


class QueryExecutor:
    """Executes SQL on any SQLAlchemy-supported database"""

    MAX_ROWS = 1000  # Safety limit

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def execute(self, sql: str) -> ExecutionResult:
        start = time.time()
        try:
            engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10}
                if "postgresql" in self.connection_string else {},
            )

            with engine.connect() as conn:
                result = conn.execute(text(sql))

                # Only fetch for SELECT-like queries
                if result.returns_rows:
                    columns = list(result.keys())
                    all_rows = result.fetchmany(self.MAX_ROWS + 1)
                    truncated = len(all_rows) > self.MAX_ROWS
                    rows = all_rows[:self.MAX_ROWS]

                    # Serialize rows (handle datetime, Decimal, etc.)
                    serialized = []
                    for row in rows:
                        serialized.append([self._serialize(v) for v in row])

                    execution_time_ms = (time.time() - start) * 1000

                    return ExecutionResult(
                        success=True,
                        columns=columns,
                        rows=serialized,
                        row_count=len(serialized),
                        execution_time_ms=round(execution_time_ms, 2),
                        truncated=truncated,
                    )
                else:
                    conn.commit()
                    execution_time_ms = (time.time() - start) * 1000
                    return ExecutionResult(
                        success=True,
                        columns=[],
                        rows=[],
                        row_count=0,
                        execution_time_ms=round(execution_time_ms, 2),
                    )

        except SQLAlchemyError as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=round((time.time() - start) * 1000, 2),
            )
        finally:
            try:
                engine.dispose()
            except Exception:
                pass

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float, bool, str)):
            return value
        try:
            import decimal
            if isinstance(value, decimal.Decimal):
                return float(value)
        except ImportError:
            pass
        try:
            import datetime
            if isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()
        except ImportError:
            pass
        return str(value)
