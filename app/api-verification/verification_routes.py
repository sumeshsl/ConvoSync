from fastapi import APIRouter,Request
from typing import List
from pydantic import BaseModel
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

#Input for preprocessing model
class Query(BaseModel):
    id: Optional[int] = None
    usercommand: str
    source: str

#Represents a response for a query from a specific AI model
class AIResponse(BaseModel):
    response: str
    model: str

#Input for Verification Service
class QueryResult(Query):
    results: list[AIResponse]

#Output from verification service
#Input to postprocessing service
class AIQueryResponse(Query):
    result: AIResponse

router = APIRouter(prefix="/verification", tags=["Verification"])

# in-memory AI results data
results = [
    {"id": 1, "usercommand": "Command 01", "source": "Web", "results": [{ "response" :"Yes", "model": "openai"}]},
    {"id": 2, "usercommand": "Command 02", "source": "iPhone", "results": [{ "response" :"No", "model": "perplexityai"}]},
    {"id": 3, "usercommand": "Command 03", "source": "Web", "results": [{ "response" :"Yes", "model": "deepseek"}]}
]



# GET all results
@router.get("/", response_model=List[QueryResult])
def get_responses():
    return results

# GET a single result by ID
@router.get("/{response_id}", response_model=QueryResult)
def get_response(response_id: int):
    for response in results:
        if response["id"] == response_id:
            return response
    return {"error": "Query not found"}


# POST request verification on the AI responses
@router.post("/", response_model=QueryResult)
def request_post_processing(result: QueryResult):
    logger.info("Entered post processing POST request")
    result_dict = result.dict()
    results.append(result_dict)
    return AIQueryResponse(**result_dict)





