import redis.asyncio as redis
from core.config import settings

_redis = None

async def init_redis():
    global _redis
    _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def close_redis():
    if _redis:
        await _redis.aclose()

def get_redis():
    return _redis