import json
from functools import lru_cache
from typing import Any
from typing import Optional

from loguru import logger
from redis import ConnectionError
from redis import Redis
from redis import RedisError
from redis import TimeoutError

from env import get_settings


@lru_cache()
def get_redis() -> Optional[Redis]:
    """Get Redis connection with automatic reconnection handling"""
    try:
        settings = get_settings()
        redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
            socket_timeout=2,  # Shorter timeout for faster fallback
            socket_connect_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # Test connection
        redis_client.ping()
        return redis_client
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis connection failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Redis error: {str(e)}")
        return None


def get_cached_data(key: str) -> Optional[dict]:
    """
    Get data from Redis cache with graceful error handling.
    Returns None if Redis is unavailable or key doesn't exist.
    """
    try:
        redis = get_redis()
        if not redis:
            return None

        data = redis.get(key)
        return json.loads(data) if data else None
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis get operation failed: {str(e)}")
        return None
    except RedisError as e:
        logger.error(f"Redis error during get: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during cache get: {str(e)}")
        return None


def set_cached_data(key: str, data: Any, expire_seconds: int = 3600) -> bool:
    """
    Set data in Redis cache with graceful error handling.
    Returns True if successful, False otherwise.
    """
    try:
        redis = get_redis()
        if not redis:
            return False

        redis.setex(name=key, time=expire_seconds, value=json.dumps(data))
        return True
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis set operation failed: {str(e)}")
        return False
    except RedisError as e:
        logger.error(f"Redis error during set: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during cache set: {str(e)}")
        return False
