"""
History Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional
from uuid import UUID

from db.session import get_db
from core.auth import get_current_user
from models.models import User, QueryHistory

router = APIRouter()


@router.get("/")
async def get_history(
    limit: int = 30,
    offset: int = 0,
    connection_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(QueryHistory)
        .where(QueryHistory.user_id == current_user.id)
    )
    if connection_id:
        query = query.where(QueryHistory.connection_id == connection_id)

    result = await db.execute(
        query.order_by(QueryHistory.created_at.desc()).limit(limit).offset(offset)
    )
    queries = result.scalars().all()
    return [
        {
            "id": str(q.id),
            "natural_language": q.natural_language,
            "generated_sql": q.generated_sql,
            "status": q.status.value if q.status else "unknown",
            "row_count": q.row_count,
            "tokens_used": q.tokens_used,
            "execution_time_ms": q.execution_time_ms,
            "guardrail_triggered": q.guardrail_triggered,
            "guardrail_reason": q.guardrail_reason,
            "eval_scores": q.eval_scores,
            "created_at": q.created_at.isoformat(),
            "connection_id": str(q.connection_id) if q.connection_id else None,
        }
        for q in queries
    ]


@router.delete("/clear")
async def clear_history(
    connection_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear history — for a specific connection or all"""
    query = delete(QueryHistory).where(QueryHistory.user_id == current_user.id)
    if connection_id:
        query = query.where(QueryHistory.connection_id == connection_id)

    result = await db.execute(query)
    await db.commit()
    return {"deleted": result.rowcount}