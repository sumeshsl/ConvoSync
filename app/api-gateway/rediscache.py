import json
from bson import ObjectId
import redis

# ✅ Connect to Redis
redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

async def cache_exists(cache_key):
    return redis_client.exists(cache_key)

async def get_redis_cache(cache_key):
    return redis_client.get(cache_key)


async def set_redis_cache(user_id,session_id,data,ttl=600):
    json_data = json.dumps(serialize_mongo_data(data))
    return redis_client.setex(f"querycache:{user_id}:{session_id}", ttl, json_data)

# 🔹 Helper Function: Convert ObjectId to string
def serialize_mongo_data(data):
    """Recursively convert MongoDB ObjectId to string for JSON serialization."""
    if isinstance(data, list):
        return [serialize_mongo_data(item) for item in data]
    elif isinstance(data, dict):
        return {key: serialize_mongo_data(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)  # ✅ Convert ObjectId to string
    else:
        return data

def store_session(user_id, session_id, jwt_token, ttl=3600):
    """Store session in Redis with expiration (1 hour)."""
    redis_client.setex(f"session:{user_id}:{session_id}", ttl, jwt_token)

def logout_user(user_id, session_id):
    """Remove the session from Redis to invalidate JWT."""
    redis_client.delete(f"session:{user_id}:{session_id}")