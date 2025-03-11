import json
from bson import ObjectId
from typing import Any,Union,Optional
import redis, os
from datetime import timedelta

# Configuration from environment variables with defaults
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_DB = int(os.getenv("REDIS_DB"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
DEFAULT_CACHE_TTL = int(os.getenv("DEFAULT_CACHE_TTL", "600"))  # 10 minutes
DEFAULT_SESSION_TTL = int(os.getenv("DEFAULT_SESSION_TTL", "3600"))

# Create Redis client with connection pool for better performance
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_timeout=5,  # Connection timeout
    socket_connect_timeout=5,  # Socket connect timeout
    retry_on_timeout=True,  # Auto retry on timeout
)

# Connect to Redis
redis_client = redis.Redis(connection_pool=redis_pool)

async def get_redis_cache(cache_key) -> Optional[str]:
    """
        Get value from Redis cache.
        Args:
            cache_key: Redis key to retrieve
        Returns:
            Cache value or None if key doesn't exist or error occurs
        """
    try:
        return redis_client.get(cache_key)
    except redis.RedisError as e:
        # Log the error instead of silently failing
        print(f"Redis error when retrieving cache: {e}")
        return None

async def set_redis_cache(cache_key:str,
                          data:Any,
                          ttl=DEFAULT_CACHE_TTL)->bool:
    """
    Store data in Redis cache with expiration.
    Args:
       cache_key: cache key to store
       data: Data to store in cache
       ttl: Time to live in seconds
    Returns:
       True if successfully set, False otherwise
    """
    try:
        json_data = json.dumps(serialize_mongo_data(data))
        return redis_client.setex(cache_key, ttl, json_data)
    except (redis.RedisError, TypeError, ValueError) as e:
        # Log the error instead of silently failing
        print(f"Error setting Redis cache: {e}")
        return False


# 🔹 Helper Function: Convert ObjectId to string
def serialize_mongo_data(data:Any)->Any:
    """
    Recursively convert MongoDB ObjectId to string for JSON serialization.
    Args:
        data: The MongoDB data object to serialize
    Returns:
        Serialized data with ObjectId converted to strings
    """
    if isinstance(data, list):
        return [serialize_mongo_data(item) for item in data]
    elif isinstance(data, dict):
        return {key: serialize_mongo_data(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

def store_session(
        user_id: str,
        session_id: str,
        jwt_token: str,
        ttl: Union[int, timedelta] = DEFAULT_SESSION_TTL
) -> bool:
    """
    Store session in Redis with expiration.
    Args:
        user_id: User identifier
        session_id: Session identifier
        jwt_token: JWT token to store
        ttl: Time to live in seconds or as timedelta
    Returns:
        True if successfully set, False otherwise
    """
    session_key = f"session:{user_id}:{session_id}"

    # Convert timedelta to seconds if needed
    if isinstance(ttl, timedelta):
        ttl = int(ttl.total_seconds())

    try:
        return redis_client.setex(session_key, ttl, jwt_token)
    except redis.RedisError as e:
        # Log the error instead of silently failing
        print(f"Error storing session: {e}")
        return False


