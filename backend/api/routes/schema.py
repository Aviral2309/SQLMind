"""
Schema Routes — DB connection management + schema introspection endpoints
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import structlog

from db.session import get_db
from core.auth import get_current_user
from models.models import User, DatabaseConnection
from db.connection_manager import ConnectionManager
from agents.schema_agent import SchemaAgent

log = structlog.get_logger()
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class AddConnectionRequest(BaseModel):
    name: str
    db_type: str  # postgres | mysql | sqlite
    connection_string: str  # e.g. postgresql://user:pass@host:5432/dbname


class ConnectionResponse(BaseModel):
    id: str
    name: str
    db_type: str
    is_active: bool
    last_tested_at: Optional[str]
    created_at: str


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    is_primary_key: bool


class TableInfo(BaseModel):
    name: str
    columns: List[ColumnInfo]
    row_count: Optional[int]
    foreign_keys: List[dict]


# ── Connection Management ─────────────────────────────────────────────────────

@router.post("/connections", response_model=ConnectionResponse, status_code=201)
async def add_connection(
    payload: AddConnectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new database connection. Tests connection before saving."""
    manager = ConnectionManager(db)
    try:
        conn = await manager.add_connection(
            user_id=current_user.id,
            name=payload.name,
            db_type=payload.db_type,
            connection_string=payload.connection_string,
        )
        return ConnectionResponse(
            id=str(conn.id),
            name=conn.name,
            db_type=conn.db_type,
            is_active=conn.is_active,
            last_tested_at=conn.last_tested_at.isoformat() if conn.last_tested_at else None,
            created_at=conn.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections", response_model=List[ConnectionResponse])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active database connections for current user."""
    manager = ConnectionManager(db)
    connections = await manager.list_connections(current_user.id)
    return [
        ConnectionResponse(
            id=str(c.id),
            name=c.name,
            db_type=c.db_type,
            is_active=c.is_active,
            last_tested_at=c.last_tested_at.isoformat() if c.last_tested_at else None,
            created_at=c.created_at.isoformat(),
        )
        for c in connections
    ]


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    manager = ConnectionManager(db)
    deleted = await manager.delete_connection(connection_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.post("/connections/{connection_id}/test")
async def test_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test an existing saved connection."""
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent()
    connection_string = agent._decrypt(conn.connection_string_encrypted)

    from agents.schema_agent import DBInspector
    inspector = DBInspector(connection_string)
    ok, error = inspector.connect()

    return {
        "success": ok,
        "message": "Connection successful" if ok else f"Failed: {error}",
    }


# ── Schema Introspection ──────────────────────────────────────────────────────

@router.get("/connections/{connection_id}/tables", response_model=List[TableInfo])
async def get_tables(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full schema of a database connection.
    Returns all tables with columns, types, PKs, FKs.
    Used by the frontend Schema Explorer component.
    """
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(conn.connection_string_encrypted)

    try:
        tables = await agent.introspect_and_return_all(connection_string)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return [
        TableInfo(
            name=t.name,
            columns=[
                ColumnInfo(
                    name=c["name"],
                    type=c["type"],
                    nullable=c["nullable"],
                    is_primary_key=c["name"] in t.primary_keys,
                )
                for c in t.columns
            ],
            row_count=t.row_count,
            foreign_keys=t.foreign_keys,
        )
        for t in tables
    ]


@router.post("/connections/{connection_id}/embed")
async def embed_schema(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger schema embedding into pgvector.
    Called after adding a connection to pre-populate RAG.
    """
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    schema_result = await agent.get_relevant_schema(
        connection_id=str(connection_id),
        natural_language="all tables",
        db_type=conn.db_type,
        force_refresh=True,
    )

    return {
        "success": True,
        "tables_embedded": schema_result.table_count,
        "columns_total": schema_result.column_count,
    }