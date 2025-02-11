from fastapi import APIRouter,Request, HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError
from app.database.mongodb import queries_collection, get_next_id
from app.schemas import Query, AIQueryResponse, AIResponse
from typing import List
import traceback
import logging
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["Queries"])

# in-memory query data
queries = []

# Define backend microservices URLs
POSTPROCESSING_API_URL = "http://api-postprocessing:8004/postprocessing/"

# GET all items
@router.get("/", response_model=List[Query])
async def get_queries():
    queriesdb = await queries_collection.find().to_list(100)
    for query in queriesdb:
        queries.append(query)
        if "id" not in query:  # If `id` is missing, use `_id`
            query["id"] = str(query["_id"])  # Convert ObjectId to string
    return queriesdb

# GET a single item by ID
@router.get("/{query_id}", response_model=Query)
async def get_query(query_id: int):
    query = await queries_collection.find_one({"id": query_id})
    if query:
        return query
    raise HTTPException(status_code=404, reason="Query not found")

# POST a new query
@router.post("/", response_model=Query)
async def create_query(query: Query,request: Request):
    await get_queries()
    query_dict = query.dict()
    try:

        query_dict["id"] = await get_next_id()
        logger.info(f"New query: {query_dict}")
        result = await queries_collection.insert_one(query_dict)

        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Insert failed: No ID returned")

        queries.append(query_dict)

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

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(POSTPROCESSING_API_URL, json=ai_query_response.dict())

                if response.status_code != 200:
                    raise HTTPException(status_code=500,
                                        detail=f"Failed to send AIQueryResponse to external API: {response.text}")

            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP Error: {http_err.response.status_code} - {http_err.response.text}")
                raise HTTPException(status_code=http_err.response.status_code,
                                    detail=f"External API Error: {http_err.response.text}")

            except httpx.RequestError as req_err:
                logger.error(f"Request Error: {str(req_err)}")
                raise HTTPException(status_code=500,
                                    detail=f"Failed to send request to postprocessing API: {str(req_err)}")

            except ValueError:
                raise HTTPException(status_code=500,
                                    detail=f"Invalid JSON received from postprocessing API: {response.text}")

            except Exception as e:
                error_type = type(e).__name__  # Get the exception type
                error_details = traceback.format_exc()  # Get full traceback
                logger.error(f"Exception Type: {error_type}\nDetails: {error_details}")
                raise HTTPException(status_code=500, detail=f"Unexpected error ({error_type}): {str(e)}")

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

    except Exception as e:

        error_type = type(e).__name__  # Get the exception type
        error_details = traceback.format_exc()  # Get full traceback
        logger.error(f"Exception Type: {error_type}\nDetails: {error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error ({error_type}): {str(e)}"
        )

    return {**query_dict, "inserted_id": str(result.inserted_id)}


