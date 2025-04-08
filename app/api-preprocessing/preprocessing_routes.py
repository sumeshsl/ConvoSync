from fastapi import APIRouter,Request, HTTPException
from fastapi.background import BackgroundTasks
from pymongo.errors import DuplicateKeyError, PyMongoError
from mongodb import queries_collection,get_next_id
from rediscache import get_redis_cache, set_redis_cache, delete_redis_cache,send_event
from schemas import Query,AIQueryResponse,AIResponse
from schemas import QueryMetadata,ChatHistory,ChatData,ChatMetadata,UserRole
from typing import List
import traceback, logging, httpx, json
from datetime import datetime
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["Queries"])


def serialize_for_json(obj):
    """Helper function to serialize objects that aren't JSON serializable by default"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UserRole):
        return obj.value
    raise TypeError(f"Type {type(obj)} not serializable")

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

    #  Check if data exists in Redis cache
    cache_key = f"querycache:{user_id}:{session_id}"
    cached_data = await get_redis_cache(cache_key)
    if cached_data:
        logger.info("Returning cached data")
        return json.loads(cached_data)  # Return cached data

    # If not cached, fetch from MongoDB
    queries_db = await queries_collection.find({"user_id": user_id,"session_id": session_id}).to_list(100)

    await set_redis_cache(cache_key,queries_db)
    logger.info(f"After setting redis cache")

    return queries_db

@router.get("/chathistory", response_model=None)
async def get_chat_history(request: Request):
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

    #  Check if data exists in Redis cache
    cache_key = f"chathistory:{user_id}:{session_id}"
    cached_data = await get_redis_cache(cache_key)
    if cached_data:
        logger.info("Returning chat history data")
        try:
            # Try to directly parse as JSON
            return json.loads(cached_data)
        except json.JSONDecodeError:
            # If that fails, it might be a JSON string inside a string
            try:
                print("Exception caught")
                # Remove escape characters and then parse
                cleaned_data = cached_data.replace('\\', '')
                if cleaned_data.startswith('"') and cleaned_data.endswith('"'):
                    cleaned_data = cleaned_data[1:-1]
                return json.loads(cleaned_data)
            except Exception as e:
                logger.error(f"Error parsing chat history: {str(e)}")
                # Fall back to returning the raw data as a string
                return {"raw_data": cached_data}

    # If no chat history found, return an empty ChatHistory as a dict
    empty_history = ChatHistory(
        user_id=user_id,
        session_id=session_id,
        metadata=ChatMetadata(
            created_at=datetime.now().isoformat(),
            last_updated_at=datetime.now().isoformat(),
            app_id="default_app"
        ),
        messages=[]
    )
    return empty_history.dict()

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
    query_dict = query.dict()
    try:

        """Retrieve user-specific data from Request."""
        user_id = request.headers.get("user-id")
        session_id = request.headers.get("session-id")

        if not user_id or not session_id:
            raise HTTPException(status_code=401, detail="Unauthorized: Missing session data")

        query_dict["id"] = await get_next_id()
        query_dict["user_id"] = user_id
        query_dict["session_id"] = session_id
        query_dict["metadata"]["timestamp"]= datetime.now().isoformat()
        logger.info(f"New query: {query_dict}")
        result = await queries_collection.insert_one(query_dict)

        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Insert failed: No ID returned")


        #test2va_service(query, user_id, session_id)
        cache_key = f"querycache:{user_id}:{session_id}"

        # Invalidate (Delete) Redis Cache for `get_queries()`
        delete_redis_cache(cache_key)
        logger.info("Redis cache invalidated after inserting new query.")

        # Fetch updated queries from MongoDB
        queriesdb = await queries_collection.find({"user_id": user_id,"session_id": session_id}).to_list(100)

        # Store the updated queries in Redis
        await set_redis_cache(cache_key, queriesdb)
        logger.info("Redis cache updated with new changes.")

        ai_response = AIResponse(
            response="Yes",
            model="ChatGPT"
        )

        metadata = QueryMetadata(
            timestamp=query_dict["metadata"]["timestamp"],
            app_id=query_dict["metadata"]["app_id"],
            needs_verification=query_dict["metadata"]["needs_verification"]
        )

        ai_query_response = AIQueryResponse(
            id=query_dict.get("id"),
            user_id=query_dict.get("user_id"),
            session_id=query_dict.get("session_id"),
            usercommand=query_dict["usercommand"],
            metadata=metadata,
            result=ai_response
        )

        background_tasks.add_task(send_event,ai_query_response)


        chat_history_cache_key = f"chathistory:{user_id}:{session_id}"
        #Updating chat history
        chat_history = await get_redis_cache(chat_history_cache_key)

        user_chat = ChatData(
            #TODO: Needs to generate ids
            timestamp=query_dict["metadata"]["timestamp"],
            role= UserRole.User,
            usercommand=query_dict["usercommand"]
        )
        assistant_chat = ChatData(
            timestamp=datetime.now().isoformat(),
            role= UserRole.Assistant,
            usercommand=ai_response.response
        )
        if not chat_history :

            chat_history = ChatHistory(
                user_id=query_dict.get("user_id"),
                session_id=query_dict.get("session_id"),
                metadata=ChatMetadata(
                    created_at=datetime.now().isoformat(),
                    last_updated_at=datetime.now().isoformat(),
                    app_id=query_dict["metadata"]["app_id"]
                ),
                messages= [user_chat,assistant_chat]
            )

        else:
            print(f"Raw chat_history: {chat_history}")

            # First json.loads to get the inner string
            chat_history_parsed = json.loads(chat_history)

            # If the result is still a string, load it again
            if isinstance(chat_history_parsed, str):
                chat_history_dict = json.loads(chat_history_parsed)
            else:
                chat_history_dict = chat_history_parsed

            print(f"Double-parsed chat_history_dict type: {type(chat_history_dict)}")
            print(f"Double-parsed chat_history_dict: {chat_history_dict}")

            # Now the rest of your code should work
            if "messages" in chat_history_dict and isinstance(chat_history_dict["messages"], list):
                chat_history_dict["messages"].append(user_chat.dict())
                chat_history_dict["messages"].append(assistant_chat.dict())
            else:
                chat_history_dict["messages"] = [user_chat.dict(), assistant_chat.dict()]

            if "metadata" in chat_history_dict:
                chat_history_dict["metadata"]["last_updated_at"] = datetime.now().isoformat()

            chat_history = ChatHistory.parse_obj(chat_history_dict)


        print("********************")
        # Then modify how you save the chat history
        chat_history_dict = chat_history.dict()
        chat_history_json = json.dumps(chat_history_dict, default=serialize_for_json)
        await set_redis_cache(chat_history_cache_key, chat_history_json)
        logger.info(f"After setting redis chat history cache")

        # Return response from both MongoDB insert & API call
        return Query(
            id=query_dict["id"],
            user_id=query_dict["user_id"],
            session_id=query_dict["session_id"],
            usercommand=query_dict["usercommand"],
            metadata = query_dict["metadata"]
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


