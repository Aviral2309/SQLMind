"""
Connection Manager — manages user's target database connections

Handles:
- Adding new connections (with encryption)
- Testing connections
- Listing user's connections
- Deleting connections
"""
from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from models.models import DatabaseConnection
from agents.schema_agent import DBInspector, SchemaAgent

log = structlog.get_logger()

SUPPORTED_DB_TYPES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
    "mssql": "mssql+pyodbc",
}


class ConnectionManager:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_connection(
        self,
        user_id: UUID,
        name: str,
        db_type: str,
        connection_string: str,
    ) -> DatabaseConnection:
        """Add a new DB connection after testing it"""

        # Normalize db_type
        db_type = db_type.lower()
        if db_type not in SUPPORTED_DB_TYPES:
            raise ValueError(f"Unsupported DB type: {db_type}. Supported: {list(SUPPORTED_DB_TYPES.keys())}")

        # Test connection before saving
        ok, error = self._test_connection(connection_string)
        if not ok:
            raise ValueError(f"Connection test failed: {error}")

        # Encrypt connection string
        encrypted = SchemaAgent.encrypt(connection_string)

        conn = DatabaseConnection(
            user_id=user_id,
            name=name,
            db_type=db_type,
            connection_string_encrypted=encrypted,
            is_active=True,
        )
        self.db.add(conn)
        await self.db.commit()
        await self.db.refresh(conn)

        log.info("connection_added", user_id=str(user_id), name=name, db_type=db_type)
        return conn

    async def test_existing_connection(self, connection_id: UUID, user_id: UUID) -> tuple[bool, str]:
        result = await self.db.execute(
            select(DatabaseConnection).where(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            return False, "Connection not found"

        from datetime import datetime
        from agents.schema_agent import SchemaAgent
        agent = SchemaAgent()
        connection_string = agent._decrypt(conn.connection_string_encrypted)
        ok, error = self._test_connection(connection_string)

        conn.last_tested_at = datetime.utcnow()
        await self.db.commit()

        return ok, error or "Connection successful"

    async def list_connections(self, user_id: UUID) -> List[DatabaseConnection]:
        result = await self.db.execute(
            select(DatabaseConnection).where(
                DatabaseConnection.user_id == user_id,
                DatabaseConnection.is_active == True,
            ).order_by(DatabaseConnection.created_at.desc())
        )
        return result.scalars().all()

    async def delete_connection(self, connection_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(DatabaseConnection).where(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            return False
        conn.is_active = False
        await self.db.commit()
        return True

    def _test_connection(self, connection_string: str) -> tuple[bool, Optional[str]]:
        """Synchronous connection test"""
        inspector = DBInspector(connection_string)
        return inspector.connect()