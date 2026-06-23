"""
SQLMind — FastAPI Application
"""
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from core.config import settings
from core.logging import setup_logging
from db.session import init_db, close_db
from db.redis_client import init_redis, close_redis
from api.routes import auth, query, schema, history, eval_routes, health
from api.routes.file_routes import router as file_router
from api.routes.insights import router as insights_router
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_id import RequestIDMiddleware
from api.websocket.endpoints import ws_router

setup_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SQLMind starting up")
    await init_db()
    await init_redis()
    log.info("SQLMind ready")
    yield
    log.info("SQLMind shutting down")
    await close_db()
    await close_redis()


app = FastAPI(
    title="SQLMind API",
    description="Agentic Text-to-SQL Data Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/v1/query", tags=["query"])
app.include_router(schema.router, prefix="/api/v1/schema", tags=["schema"])
app.include_router(history.router, prefix="/api/v1/history", tags=["history"])
app.include_router(file_router, prefix="/api/v1/files", tags=["files"])
app.include_router(insights_router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(ws_router)
app.include_router(eval_routes.router, prefix="/api/v1/eval", tags=["eval"])