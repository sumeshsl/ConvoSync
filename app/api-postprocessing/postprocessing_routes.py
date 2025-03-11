from fastapi import APIRouter,Request
from typing import List
import logging
import asyncio
import websockets
from schemas import AIQueryResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/postprocessing", tags=["PostProcessing"])

# in-memory AI response data
responses = []



# # GET all responses
# @router.get("/", response_model=List[AIQueryResponse])
# def get_responses():
#     return responses
#
# # GET a single response by ID
# @router.get("/{response_id}", response_model=AIQueryResponse)
# def get_response(response_id: int):
#     for response in responses:
#         if response["id"] == response_id:
#             return response
#     return {"error": "Query not found"}


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
