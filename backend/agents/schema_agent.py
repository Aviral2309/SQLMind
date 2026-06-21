"""
Schema Agent — with Redis caching + fallback to full schema (no embedding needed)
Embedding is optional — if it fails, full schema is used directly
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
import structlog

log = structlog.get_logger()
SCHEMA_CACHE_TTL = 3600  # 1 hour


@dataclass
class SchemaResult:
    schema_text: str = ""
    relevant_tables: List[str] = field(default_factory=list)
    rag_chunks: List[dict] = field(default_factory=list)
    table_count: int = 0
    column_count: int = 0


@dataclass
class TableInfo:
    name: str
    columns: List[dict]
    primary_keys: List[str]
    foreign_keys: List[dict]
    row_count: Optional[int] = None


class DBInspector:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._engine = None

    def connect(self):
        try:
            kwargs = {}
            if "postgresql" in self.connection_string:
                kwargs["connect_args"] = {"connect_timeout": 10}
            self._engine = create_engine(
                self.connection_string, pool_pre_ping=True, **kwargs
            )
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, None
        except SQLAlchemyError as e:
            return False, str(e)

    def get_all_tables(self) -> List[TableInfo]:
        if not self._engine:
            raise RuntimeError("Not connected")
        inspector = inspect(self._engine)
        tables = []
        for table_name in inspector.get_table_names():
            try:
                columns = [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                    }
                    for col in inspector.get_columns(table_name)
                ]
                pk = inspector.get_pk_constraint(table_name)
                primary_keys = pk.get("constrained_columns", [])
                fks = [
                    {
                        "columns": fk.get("constrained_columns", []),
                        "referred_table": fk.get("referred_table", ""),
                        "referred_columns": fk.get("referred_columns", []),
                    }
                    for fk in inspector.get_foreign_keys(table_name)
                ]
                row_count = None
                try:
                    with self._engine.connect() as conn:
                        if "postgresql" in self.connection_string:
                            r = conn.execute(text(
                                f"SELECT reltuples::bigint FROM pg_class WHERE relname = '{table_name}'"
                            ))
                        else:
                            r = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                        row_count = r.scalar()
                except Exception:
                    pass
                tables.append(TableInfo(
                    name=table_name, columns=columns,
                    primary_keys=primary_keys, foreign_keys=fks,
                    row_count=row_count,
                ))
            except Exception as e:
                log.warning("table_introspect_failed", table=table_name, error=str(e))
        return tables

    def close(self):
        if self._engine:
            self._engine.dispose()


class SchemaFormatter:
    def format_full_schema(self, tables: List[TableInfo]) -> str:
        lines = []
        for t in tables:
            lines.append(f"TABLE: {t.name}")
            if t.row_count is not None:
                lines.append(f"  Rows: ~{t.row_count:,}")
            lines.append("  COLUMNS:")
            for col in t.columns:
                pk = " [PK]" if col["name"] in t.primary_keys else ""
                lines.append(f"    - {col['name']} ({col['type']}){pk}")
            if t.foreign_keys:
                lines.append("  FOREIGN KEYS:")
                for fk in t.foreign_keys:
                    cols = ", ".join(fk["columns"])
                    ref = fk["referred_table"]
                    ref_cols = ", ".join(fk["referred_columns"])
                    lines.append(f"    - {cols} -> {ref}({ref_cols})")
            lines.append("")
        return "\n".join(lines)

    def format_table_chunk(self, t: TableInfo) -> str:
        col_list = ", ".join(
            f"{c['name']} {c['type']}{'[PK]' if c['name'] in t.primary_keys else ''}"
            for c in t.columns
        )
        fk_list = ""
        if t.foreign_keys:
            parts = [
                f"{','.join(fk['columns'])} references {fk['referred_table']}"
                for fk in t.foreign_keys
            ]
            fk_list = f" Foreign keys: {'; '.join(parts)}."
        return f"Table {t.name} has columns: {col_list}.{fk_list}"


class SchemaAgent:
    def __init__(self, app_db_session=None):
        self.session = app_db_session
        self.formatter = SchemaFormatter()

    async def get_relevant_schema(
        self,
        connection_id: str,
        natural_language: str,
        db_type: str,
        connection_string: str = None,
        force_refresh: bool = False,
    ) -> SchemaResult:

        if not self.session:
            return SchemaResult(schema_text="-- Schema introspection requires DB session")

        if not connection_string:
            connection_string = await self._load_connection_string(connection_id)
        if not connection_string:
            return SchemaResult(schema_text="-- Connection not found")

        # ── Redis cache for schema structure ──────────────────────────────
        redis_client = None
        cache_key = f"schema_full:{connection_id}"
        tables = None

        try:
            from db.redis_client import get_redis
            redis_client = get_redis()
            if redis_client and not force_refresh:
                cached = await redis_client.get(cache_key)
                if cached:
                    log.info("schema_cache_hit", connection_id=connection_id)
                    td = json.loads(cached)
                    tables = [
                        TableInfo(
                            name=t["name"], columns=t["columns"],
                            primary_keys=t["primary_keys"], foreign_keys=t["foreign_keys"],
                            row_count=t.get("row_count"),
                        )
                        for t in td
                    ]
        except Exception as e:
            log.warning("redis_cache_failed", error=str(e))

        # ── Introspect DB if not cached ───────────────────────────────────
        if tables is None:
            inspector = DBInspector(connection_string)
            ok, error = inspector.connect()
            if not ok:
                return SchemaResult(schema_text=f"-- Could not connect: {error}")
            try:
                tables = inspector.get_all_tables()
            finally:
                inspector.close()

            if not tables:
                return SchemaResult(schema_text="-- No tables found")

            # Save to Redis
            if redis_client:
                try:
                    await redis_client.setex(
                        cache_key, SCHEMA_CACHE_TTL,
                        json.dumps([
                            {
                                "name": t.name, "columns": t.columns,
                                "primary_keys": t.primary_keys,
                                "foreign_keys": t.foreign_keys,
                                "row_count": t.row_count,
                            }
                            for t in tables
                        ])
                    )
                    log.info("schema_cached", connection_id=connection_id, tables=len(tables))
                except Exception as e:
                    log.warning("redis_cache_set_failed", error=str(e))

        full_schema = self.formatter.format_full_schema(tables)
        all_table_names = [t.name for t in tables]

        # ── RAG retrieval — optional, fallback to full schema ─────────────
        rag_chunks = []
        relevant_tables = []

        try:
            from models.models import SchemaEmbedding
            from sqlalchemy import select, delete
            from core.config import settings

            # Try pgvector retrieval only if OpenAI key available
            if settings.OPENAI_API_KEY:
                from langchain_openai import OpenAIEmbeddings
                embedder = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=settings.OPENAI_API_KEY,
                )

                query_embedding = await embedder.aembed_query(natural_language)
                result = await self.session.execute(
                    select(SchemaEmbedding)
                    .where(SchemaEmbedding.connection_id == connection_id)
                    .order_by(SchemaEmbedding.embedding.cosine_distance(query_embedding))
                    .limit(5)
                )
                rows = result.scalars().all()
                rag_chunks = [
                    {"table_name": r.table_name, "schema_text": r.schema_text}
                    for r in rows
                ]

                # Embed if not yet done
                if not rag_chunks or force_refresh:
                    await self.session.execute(
                        delete(SchemaEmbedding).where(SchemaEmbedding.connection_id == connection_id)
                    )
                    chunks = [
                        {"table_name": t.name, "text": self.formatter.format_table_chunk(t)}
                        for t in tables
                    ]
                    texts = [c["text"] for c in chunks]
                    embeddings = await embedder.aembed_documents(texts)
                    for chunk, emb in zip(chunks, embeddings):
                        self.session.add(SchemaEmbedding(
                            connection_id=connection_id,
                            table_name=chunk["table_name"],
                            schema_text=chunk["text"],
                            embedding=emb,
                            metadata_={"table_name": chunk["table_name"]},
                        ))
                    await self.session.commit()

                    # Re-retrieve
                    result2 = await self.session.execute(
                        select(SchemaEmbedding)
                        .where(SchemaEmbedding.connection_id == connection_id)
                        .order_by(SchemaEmbedding.embedding.cosine_distance(query_embedding))
                        .limit(5)
                    )
                    rows2 = result2.scalars().all()
                    rag_chunks = [
                        {"table_name": r.table_name, "schema_text": r.schema_text}
                        for r in rows2
                    ]

                relevant_tables = list({chunk["table_name"] for chunk in rag_chunks})

        except Exception as e:
            log.warning("rag_retrieval_failed_using_full_schema", error=str(e))
            rag_chunks = []
            relevant_tables = []

        # Keyword-based table matching as fallback
        nl_lower = natural_language.lower()
        for tn in all_table_names:
            if tn.lower() in nl_lower and tn not in relevant_tables:
                relevant_tables.append(tn)

        # If still no relevant tables, use all
        if not relevant_tables:
            relevant_tables = all_table_names

        # Schema text selection
        if len(tables) <= 15 or not rag_chunks:
            # Small DB or no RAG — use full schema always
            schema_text = full_schema
        else:
            rel_objs = [t for t in tables if t.name in relevant_tables]
            schema_text = self.formatter.format_full_schema(rel_objs)
            schema_text += f"\n-- Total tables: {len(tables)} (showing {len(rel_objs)} relevant)"

        return SchemaResult(
            schema_text=schema_text,
            relevant_tables=relevant_tables,
            rag_chunks=rag_chunks,
            table_count=len(tables),
            column_count=sum(len(t.columns) for t in tables),
        )

    async def introspect_and_return_all(self, connection_string: str) -> List[TableInfo]:
        inspector = DBInspector(connection_string)
        ok, error = inspector.connect()
        if not ok:
            raise ValueError(f"Connection failed: {error}")
        try:
            return inspector.get_all_tables()
        finally:
            inspector.close()

    async def _load_connection_string(self, connection_id: str) -> Optional[str]:
        from models.models import DatabaseConnection
        from sqlalchemy import select
        result = await self.session.execute(
            select(DatabaseConnection).where(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.is_active == True,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            return None
        return self._decrypt(conn.connection_string_encrypted)

    def _decrypt(self, encrypted: str) -> str:
        import base64
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except Exception:
            return encrypted

    @staticmethod
    def encrypt(connection_string: str) -> str:
        import base64
        return base64.b64encode(connection_string.encode()).decode()