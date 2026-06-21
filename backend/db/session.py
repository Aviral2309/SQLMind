from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from core.config import settings

engine = create_async_engine(settings.ASYNC_POSTGRES_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Models import karo yahan — circular import avoid karne ke liye
        from models import models  # noqa
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await engine.dispose()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session