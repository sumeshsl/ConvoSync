from fastapi import APIRouter,Request, HTTPException
from fastapi.background import BackgroundTasks
from pymongo.errors import DuplicateKeyError, PyMongoError
from mongodb import queries_collection,get_next_id
from rediscache import get_redis_cache, set_redis_cache, delete_redis_cache,send_event
from schemas import Query,AIQueryResponse,AIResponse
from typing import List
import traceback, logging, httpx, json

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["Queries"])

@router.get("/", response_model=List[Query])
async def get_queries(request: Request):
    """
    GET fetches all queries for a specific user session.\n
    Arguments:  \n
        request: Client request for preprocessing. \n
    Returns:  \n
        All the queries for this user.\n
    """
    user_id = request.headers.get("user-id")
    session_id = request.headers.get("session-id")

    logger.info(f"User {user_id} session {session_id}")
    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing session data")

    # ✅ Check if data exists in Redis cache
    cache_key = f"querycache:{user_id}:{session_id}"
    cached_data = await get_redis_cache(cache_key)
    if cached_data:
        logger.info("Returning cached data")
        return json.loads(cached_data)  # ✅ Return cached data

    # If not cached, fetch from MongoDB
    queriesdb = await queries_collection.find().to_list(100)

    await set_redis_cache(cache_key,queriesdb)
    logger.info(f"After setting redis cache")

    return queriesdb


# GET a single item by ID
@router.get("/{query_id}", response_model=Query)
async def get_query(query_id: int):
    """
    GET fetches a queries for a specific user session.\n
    Arguments:  \n
        response: AI query response that needs to be post-processed. \n
    Returns:  \n
        The query data requested.\n
    """
    query = await queries_collection.find_one({"id": query_id})
    if query:
        return query
    raise HTTPException(status_code=404, reason="Query not found")

# POST a new query
@router.post("/", response_model=Query)
async def create_query(query: Query,request: Request, background_tasks: BackgroundTasks):
    """
        POST Creates a query request to the server for processing.\n
        Arguments:  \n
            query: The query requested. \n
        Returns:  \n
            Processed result of the query.\n
        """
    await get_queries(request)
    query_dict = query.dict()
    try:

        query_dict["id"] = await get_next_id()
        logger.info(f"New query: {query_dict}")
        result = await queries_collection.insert_one(query_dict)

        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Insert failed: No ID returned")

        """Retrieve user-specific data from Redis cache."""
        user_id = request.headers.get("user-id")
        session_id = request.headers.get("session-id")

        cache_key = f"querycache:{user_id}:{session_id}"

        # Invalidate (Delete) Redis Cache for `get_queries()`
        delete_redis_cache(cache_key)
        logger.info("Redis cache invalidated after inserting new query.")

        # Fetch updated queries from MongoDB
        queriesdb = await queries_collection.find().to_list(100)

        # Store the updated queries in Redis
        await set_redis_cache(cache_key, queriesdb)
        logger.info("Redis cache updated with new changes.")

        ai_response = AIResponse(
            response= "Yes",
            model = "ChatGPT"
        )

        ai_query_response = AIQueryResponse(
            id=query_dict.get("id"),
            usercommand=query_dict["usercommand"],
            source=query_dict["source"],
            result=ai_response
        )

        background_tasks.add_task(send_event,ai_query_response)

        # ✅ Return response from both MongoDB insert & API call
        return Query(
            id=query_dict["id"],
            usercommand=query_dict["usercommand"],
            source=query_dict["source"]
        )


    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Duplicate key error: ID already exists")

    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")

    except Exception as e:#TODO: Clean exceptions

        error_type = type(e).__name__  # Get the exception type
        error_details = traceback.format_exc()  # Get full traceback
        logger.error(f"Exception Type: {error_type}\nDetails: {error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error ({error_type}): {str(e)}"
        )

    return {**query_dict, "inserted_id": str(result.inserted_id)}
