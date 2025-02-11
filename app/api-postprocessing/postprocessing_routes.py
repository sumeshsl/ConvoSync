from fastapi import APIRouter,Request
from typing import List
from pydantic import BaseModel
import logging
from typing import Optional
import asyncio
import websockets


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

router = APIRouter(prefix="/postprocessing", tags=["PostProcessing"])

# in-memory AI response data
responses = [
    {"id": 1, "usercommand": "Command 01", "source": "Web", "result": { "response" :"Yes", "model": "openai"}},
    {"id": 2, "usercommand": "Command 02", "source": "iPhone", "result": { "response" :"No", "model": "perplexityai"}},
    {"id": 3, "usercommand": "Command 03", "source": "Web", "result": { "response" :"Yes", "model": "deepseek"}}
]



# GET all responses
@router.get("/", response_model=List[AIQueryResponse])
def get_responses():
    return responses

# GET a single response by ID
@router.get("/{response_id}", response_model=AIQueryResponse)
def get_response(response_id: int):
    for response in responses:
        if response["id"] == response_id:
            return response
    return {"error": "Query not found"}


# POST request post-processing on the AI response
@router.post("/", response_model=AIQueryResponse)
async def request_post_processing(response: AIQueryResponse):
    logger.info("Entered post processing POST request")
    response_dict = response.dict()
    responses.append(response_dict)
    await websocket_client();
    return AIQueryResponse(**response_dict)

async def websocket_client():
    uri = "ws://api-verification:8002/ws"  # Use the service name in Docker
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello from Post processing server!")
        response = await websocket.recv()
        print(f"Response from Verification {response}")

if __name__ == "__main__":
    asyncio.run(websocket_client())
