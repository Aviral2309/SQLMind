"""
Insights Routes — auto-analysis of connected databases
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from core.auth import get_current_user
from models.models import User, DatabaseConnection
from agents.schema_agent import SchemaAgent
from agents.insight_agent import AutoInsightAgent

router = APIRouter()


@router.post("/{connection_id}")
async def generate_insights(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-analyze a database and return insight cards"""
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)

    try:
        from agents.pipeline import get_llm
        llm = get_llm(temperature=0.3)
    except Exception:
        llm = None

    insight_agent = AutoInsightAgent(llm=llm)
    report = await insight_agent.analyze(
        connection_string=connection_string,
        connection_name=connection.name,
        db_type=connection.db_type,
    )

    if report.error:
        raise HTTPException(status_code=400, detail=report.error)

    return {
        "connection_name": report.connection_name,
        "total_tables": report.total_tables,
        "total_rows": report.total_rows,
        "summary": report.summary,
        "generated_in_ms": report.generated_in_ms,
        "insights": [
            {
                "type": i.type,
                "title": i.title,
                "value": i.value,
                "detail": i.detail,
                "severity": i.severity,
                "data": i.data,
            }
            for i in report.insights
        ],
    }
