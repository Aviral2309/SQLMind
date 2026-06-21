"""
Query Routes — Phase 3 complete
"""
import time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import structlog

from db.session import get_db
from core.auth import get_current_user
from models.models import User, QueryHistory, DatabaseConnection, QueryStatusEnum
from agents.pipeline import run_sqlmind
from agents.executor import QueryExecutor
from agents.answer_agent import AnswerAgent
from agents.anomaly_detector import AnomalyDetector
from agents.query_optimizer import QueryOptimizer
from agents.schema_agent import SchemaAgent
from eval.pipeline import EvaluationPipeline
from api.routes.upload import FileUploadHandler

log = structlog.get_logger()
router = APIRouter()
eval_pipeline = EvaluationPipeline()
anomaly_detector = AnomalyDetector()
upload_handler = FileUploadHandler()


class QueryRequest(BaseModel):
    natural_language: str
    connection_id: UUID
    mode: str = "sql"
    execute: bool = True
    reference_sql: Optional[str] = None

class OptimizeRequest(BaseModel):
    sql: str
    dialect: str = "postgres"

class AnomalyRequest(BaseModel):
    connection_id: UUID
    sql: str
    value_col: Optional[str] = None
    label_col: Optional[str] = None


@router.post("/upload")
async def upload_database(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("db", "sqlite", "sqlite3", "csv"):
        raise HTTPException(status_code=400, detail="Only .db, .sqlite, .csv files supported")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 50MB.")
    try:
        if ext == "csv":
            connection_string, file_path = await upload_handler.handle_csv(content, filename)
        else:
            connection_string, file_path = await upload_handler.handle_sqlite(content, filename)
        encrypted = SchemaAgent.encrypt(connection_string)
        conn = DatabaseConnection(
            user_id=current_user.id, name=name or filename,
            db_type="sqlite", connection_string_encrypted=encrypted, is_active=True,
        )
        db.add(conn)
        await db.commit()
        await db.refresh(conn)
        return {"id": str(conn.id), "name": conn.name, "db_type": conn.db_type, "file": filename, "message": "Uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate")
async def generate_sql(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == payload.connection_id,
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)
    start_time = time.time()

    query_record = QueryHistory(
        user_id=current_user.id, connection_id=connection.id,
        natural_language=payload.natural_language, status=QueryStatusEnum.RUNNING,
    )
    db.add(query_record)
    await db.flush()

    try:
        final_state = await run_sqlmind(
            natural_language=payload.natural_language,
            connection_id=str(payload.connection_id),
            user_id=str(current_user.id),
            db_type=connection.db_type,
            connection_string=connection_string,
            db_session=db,
        )
        execution_time_ms = (time.time() - start_time) * 1000

        response = {
            "query_id": str(query_record.id),
            "status": final_state.get("status"),
            "generated_sql": final_state.get("generated_sql"),
            "explanation": final_state.get("explanation"),
            "agent_steps": final_state.get("agent_steps"),
            "tokens_used": final_state.get("tokens_used", 0),
            "model_used": final_state.get("model_used"),
            "guardrail_triggered": final_state.get("guardrail_triggered", False),
            "guardrail_reason": final_state.get("guardrail_reason"),
            "execution_time_ms": round(execution_time_ms, 2),
            "execution_result": None,
            "answer": None,
            "eval_scores": None,
        }

        if final_state.get("status") == "success" and final_state.get("generated_sql") and payload.execute:
            executor = QueryExecutor(connection_string)
            exec_result = executor.execute(final_state["generated_sql"])
            response["execution_result"] = {
                "success": exec_result.success,
                "columns": exec_result.columns,
                "rows": exec_result.rows,
                "row_count": exec_result.row_count,
                "execution_time_ms": exec_result.execution_time_ms,
                "truncated": exec_result.truncated,
                "error": exec_result.error,
            }
            if payload.mode == "qa" and exec_result.success and exec_result.rows:
                try:
                    from agents.pipeline import get_llm
                    llm = get_llm(temperature=0.3)
                    answer_agent = AnswerAgent(llm=llm)
                    response["answer"] = await answer_agent.answer(
                        question=payload.natural_language,
                        columns=exec_result.columns,
                        rows=exec_result.rows,
                        sql=final_state["generated_sql"],
                    )
                except Exception as e:
                    log.warning("answer_agent_error", error=str(e))

        if payload.reference_sql and final_state.get("generated_sql"):
            hallucination_score = 0.0
            for step in final_state.get("agent_steps", []):
                if step.get("node") == "verifier":
                    hallucination_score = step.get("hallucination_score", 0.0)
                    break
            eval_result = await eval_pipeline.evaluate(
                generated_sql=final_state["generated_sql"],
                reference_sql=payload.reference_sql,
                hallucination_score=hallucination_score,
                dialect=connection.db_type,
            )
            response["eval_scores"] = {
                "semantic_equivalence": eval_result.semantic_equivalence,
                "bleu_score": eval_result.bleu_score,
                "hallucination_rate": eval_result.hallucination_rate,
                "overall": eval_result.overall,
            }

        status = QueryStatusEnum.SUCCESS if final_state.get("status") == "success" else \
                 QueryStatusEnum.GUARDRAIL_BLOCKED if final_state.get("guardrail_triggered") else \
                 QueryStatusEnum.FAILED
        query_record.status = status
        query_record.generated_sql = final_state.get("generated_sql")
        query_record.explanation = final_state.get("explanation")
        query_record.agent_steps = final_state.get("agent_steps")
        query_record.tokens_used = final_state.get("tokens_used", 0)
        query_record.model_used = final_state.get("model_used")
        query_record.guardrail_triggered = final_state.get("guardrail_triggered", False)
        query_record.guardrail_reason = final_state.get("guardrail_reason")
        query_record.execution_time_ms = execution_time_ms
        query_record.eval_scores = response.get("eval_scores")
        if response.get("execution_result"):
            query_record.row_count = response["execution_result"].get("row_count", 0)
        await db.commit()
        return response

    except Exception as e:
        log.error("query_failed", error=str(e))
        query_record.status = QueryStatusEnum.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_sql(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    connection_id = payload.get("connection_id")
    sql = payload.get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL is required")
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)
    executor = QueryExecutor(connection_string)
    exec_result = executor.execute(sql)
    return {
        "success": exec_result.success,
        "columns": exec_result.columns,
        "rows": exec_result.rows,
        "row_count": exec_result.row_count,
        "execution_time_ms": exec_result.execution_time_ms,
        "truncated": exec_result.truncated,
        "error": exec_result.error,
    }


@router.post("/optimize")
async def optimize_query(
    payload: OptimizeRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        from agents.pipeline import get_llm
        llm = get_llm(temperature=0.1)
    except Exception:
        llm = None
    optimizer = QueryOptimizer(llm=llm)
    result = await optimizer.optimize(payload.sql, payload.dialect)
    return {
        "original_sql": result.original_sql,
        "optimized_sql": result.optimized_sql,
        "issues": [{"type": i.type, "severity": i.severity, "message": i.message, "suggestion": i.suggestion} for i in result.issues],
        "explanation": result.explanation,
        "improvement_score": result.improvement_score,
        "has_improvements": len(result.issues) > 0,
    }


@router.post("/anomaly")
async def detect_anomalies(
    payload: AnomalyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == payload.connection_id,
            DatabaseConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)
    executor = QueryExecutor(connection_string)
    exec_result = executor.execute(payload.sql)
    if not exec_result.success:
        raise HTTPException(status_code=400, detail=exec_result.error)
    detection = anomaly_detector.detect_from_query_result(
        columns=exec_result.columns, rows=exec_result.rows,
        value_col=payload.value_col, label_col=payload.label_col,
    )
    return {
        "columns": exec_result.columns,
        "rows": exec_result.rows,
        "anomalies": [{"index": a.index, "value": a.value, "label": a.label, "z_score": a.z_score, "severity": a.severity} for a in detection.anomalies],
        "stats": {"total_points": detection.total_points, "anomaly_count": detection.anomaly_count, "mean": detection.mean, "std": detection.std},
        "error": detection.error,
    }


@router.get("/history")
async def get_history(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(QueryHistory)
        .where(QueryHistory.user_id == current_user.id)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit).offset(offset)
    )
    queries = result.scalars().all()
    return [{"id": str(q.id), "natural_language": q.natural_language, "generated_sql": q.generated_sql,
             "status": q.status.value if q.status else "unknown", "row_count": q.row_count,
             "tokens_used": q.tokens_used, "execution_time_ms": q.execution_time_ms,
             "guardrail_triggered": q.guardrail_triggered, "eval_scores": q.eval_scores,
             "created_at": q.created_at.isoformat()} for q in queries]


@router.get("/stats")
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func, cast
    from sqlalchemy import Date
    from datetime import datetime, timedelta

    total = (await db.execute(select(func.count(QueryHistory.id)).where(QueryHistory.user_id == current_user.id))).scalar() or 0
    success = (await db.execute(select(func.count(QueryHistory.id)).where(QueryHistory.user_id == current_user.id, QueryHistory.status == QueryStatusEnum.SUCCESS))).scalar() or 0
    blocked = (await db.execute(select(func.count(QueryHistory.id)).where(QueryHistory.user_id == current_user.id, QueryHistory.guardrail_triggered == True))).scalar() or 0
    tokens = (await db.execute(select(func.sum(QueryHistory.tokens_used)).where(QueryHistory.user_id == current_user.id))).scalar() or 0
    connections = (await db.execute(select(func.count(DatabaseConnection.id)).where(DatabaseConnection.user_id == current_user.id, DatabaseConnection.is_active == True))).scalar() or 0
    avg_exec = (await db.execute(select(func.avg(QueryHistory.execution_time_ms)).where(QueryHistory.user_id == current_user.id, QueryHistory.status == QueryStatusEnum.SUCCESS))).scalar() or 0

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    activity_result = await db.execute(
        select(cast(QueryHistory.created_at, Date).label("date"), func.count(QueryHistory.id).label("count"))
        .where(QueryHistory.user_id == current_user.id, QueryHistory.created_at >= seven_days_ago)
        .group_by(cast(QueryHistory.created_at, Date))
        .order_by(cast(QueryHistory.created_at, Date))
    )
    activity = [{"date": str(r.date), "count": r.count} for r in activity_result]

    return {
        "user": {"email": current_user.email, "username": current_user.username, "plan": current_user.plan, "member_since": current_user.created_at.isoformat()},
        "stats": {"total_queries": total, "successful_queries": success, "success_rate": round(success/total*100, 1) if total > 0 else 0,
                  "guardrail_blocks": blocked, "total_tokens_used": tokens, "active_connections": connections, "avg_execution_ms": round(float(avg_exec), 1)},
        "activity": activity,
    }


# ── SQL File Upload ───────────────────────────────────────────────────────────

@router.post("/upload-sql")
async def upload_sql_file(
    file: UploadFile = File(...),
    connection_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a .sql file and execute it on the target connection"""
    content = await file.read()
    filename = file.filename or "upload.sql"

    if not filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Only .sql files supported")

    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")

    sql_content = content.decode("utf-8")

    # Get connection
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)

    # Execute SQL
    executor = QueryExecutor(connection_string)
    exec_result = executor.execute(sql_content)

    # Invalidate schema cache for this connection
    try:
        from db.redis_client import get_redis
        redis = get_redis()
        if redis:
            await redis.delete(f"schema_full:{connection_id}")
    except Exception:
        pass

    return {
        "filename": filename,
        "success": exec_result.success,
        "columns": exec_result.columns,
        "rows": exec_result.rows[:100],
        "row_count": exec_result.row_count,
        "execution_time_ms": exec_result.execution_time_ms,
        "error": exec_result.error,
        "message": "SQL file executed successfully" if exec_result.success else exec_result.error,
    }
