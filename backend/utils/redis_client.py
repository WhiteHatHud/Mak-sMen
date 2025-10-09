"""
Redis client configuration and connection management.
"""

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from config import settings
import logging

logger = logging.getLogger(__name__)

# Redis connection pool
_pool = None
_redis_client = None


def get_redis_pool():
    """Get or create Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20
        )
    return _pool


def get_redis_client():
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        pool = get_redis_pool()
        _redis_client = redis.Redis(connection_pool=pool)
    return _redis_client


# Global redis instance for imports
redis = get_redis_client()


async def ping_redis():
    """Test Redis connection."""
    try:
        await redis.ping()
        logger.info("Redis connection successful")
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return False


async def close_redis():
    """Close Redis connections."""
    global _redis_client, _pool
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    if _pool:
        await _pool.disconnect()
        _pool = None