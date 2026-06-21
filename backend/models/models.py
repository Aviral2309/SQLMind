"""
SQLAlchemy ORM models
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean,
    ForeignKey, Integer, Float, JSON, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from db.session import Base
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    plan = Column(String(50), default="free")  # free | pro | enterprise
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connections = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("QueryHistory", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(255), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    db_type = Column(String(50), nullable=False)  # postgres | mysql | sqlite | bigquery
    connection_string_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    last_tested_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="connections")
    queries = relationship("QueryHistory", back_populates="connection")


class QueryStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    GUARDRAIL_BLOCKED = "guardrail_blocked"


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=True)

    natural_language = Column(Text, nullable=False)
    generated_sql = Column(Text)
    explanation = Column(Text)
    status = Column(Enum(QueryStatusEnum), default=QueryStatusEnum.PENDING)

    # Execution results
    row_count = Column(Integer)
    execution_time_ms = Column(Float)
    result_preview = Column(JSONB)  # First 100 rows preview

    # Agent trace
    agent_steps = Column(JSONB)  # Full LangGraph trace
    tokens_used = Column(Integer)
    model_used = Column(String(100))

    # Guardrail info
    guardrail_triggered = Column(Boolean, default=False)
    guardrail_reason = Column(String(255))

    # Eval scores
    eval_scores = Column(JSONB)  # {accuracy, bleu, semantic_eq, hallucination_rate}

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="queries")
    connection = relationship("DatabaseConnection", back_populates="queries")


class SchemaEmbedding(Base):
    """Stores pgvector embeddings for schema-aware RAG"""
    __tablename__ = "schema_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=False)
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255))
    schema_text = Column(Text, nullable=False)  # human-readable schema description
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimension
    metadata_ = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalBenchmark(Base):
    """Stores ground-truth SQL pairs for evaluation"""
    __tablename__ = "eval_benchmarks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=True)
    natural_language = Column(Text, nullable=False)
    expected_sql = Column(Text, nullable=False)
    difficulty = Column(String(50), default="medium")  # easy | medium | hard
    tags = Column(JSONB)  # ["join", "aggregation", "subquery"]
    created_at = Column(DateTime, default=datetime.utcnow)
