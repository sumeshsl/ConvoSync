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

async def cache_exists(cache_key)-> bool:
    """
    Check if a key exists in Redis cache.
    Args:
        cache_key: Redis key to check
    Returns:
        True if key exists, False otherwise
    """
    try:
        return redis_client.exists(cache_key)
    except redis.RedisError as e:
            # Log the error instead of silently failing
            print(f"Redis error when checking key existence: {e}")
            return False

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


async def set_redis_cache(user_id:str,
                          session_id:str,
                          data:Any,
                          ttl:int=DEFAULT_CACHE_TTL)->bool:
    """
    Store data in Redis cache with expiration.
    Args:
        user_id: User identifier
        session_id: Session identifier
        data: Data to store in cache
        ttl: Time to live in seconds
    Returns:
        True if successfully set, False otherwise
    """
    cache_key = f"querycache:{user_id}:{session_id}"
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


def logout_user(user_id: str, session_id: str) -> bool:
    """
    Remove the session from Redis to invalidate JWT.
    Args:
        user_id: User identifier
        session_id: Session identifier
    Returns:
        True if successfully removed, False otherwise
    """
    session_key = f"session:{user_id}:{session_id}"
    try:
        return bool(redis_client.delete(session_key))
    except redis.RedisError as e:
        # Log the error instead of silently failing
        print(f"Error during logout: {e}")
        return False


# Add health check function
def ping_redis() -> bool:
    """
    Check if Redis connection is healthy.
    Returns:
        True if Redis responds to ping, False otherwise
    """
    try:
        return redis_client.ping()
    except redis.RedisError:
        return False


# Add method to clear all cache for a user
async def clear_user_cache(user_id: str) -> int:
    """
    Clear all cache entries for a specific user.
    Args:
        user_id: User identifier
    Returns:
        Number of keys deleted
    """
    pattern = f"querycache:{user_id}:*"
    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except redis.RedisError as e:
        print(f"Error clearing user cache: {e}")
        return 0
