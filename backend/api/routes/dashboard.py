"""
Dashboard Routes — NL-to-Dashboard endpoint
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db.session import get_db
from core.auth import get_current_user
from models.models import User, DatabaseConnection
from agents.schema_agent import SchemaAgent
from agents.dashboard_agent import DashboardAgent

router = APIRouter()


class DashboardRequest(BaseModel):
    connection_id: str
    request: str


@router.post("/generate")
async def generate_dashboard(
    payload: DashboardRequest,
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

    # Get schema context
    schema_result = await agent.get_relevant_schema(
        connection_id=payload.connection_id,
        natural_language=payload.request,
        db_type=connection.db_type,
        connection_string=connection_string,
    )

    try:
        from agents.pipeline import get_llm
        llm = get_llm(temperature=0.2)
    except Exception:
        raise HTTPException(status_code=500, detail="LLM not configured")

    dash_agent = DashboardAgent(llm=llm)
    dashboard = await dash_agent.generate(
        user_request=payload.request,
        schema_context=schema_result.schema_text,
        connection_string=connection_string,
        db_type=connection.db_type,
    )

    if dashboard.error:
        raise HTTPException(status_code=400, detail=dashboard.error)

    return {
        "title": dashboard.title,
        "description": dashboard.description,
        "generated_in_ms": dashboard.generated_in_ms,
        "widgets": [
            {
                "title": w.title,
                "description": w.description,
                "chart_type": w.chart_type,
                "columns": w.columns,
                "rows": w.rows,
                "error": w.error,
                "execution_time_ms": w.execution_time_ms,
            }
            for w in dashboard.widgets
        ],
    }
