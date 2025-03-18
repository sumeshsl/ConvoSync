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

@router.post("/", response_model=AIQueryResponse)
async def request_post_processing(response: AIQueryResponse):
    """
    POST request post-processing on the AI response to get it validated.\n
    Arguments:  \n
        response: AI query response that needs to be post-processed. \n
    Returns:  \n
        Processed query with validated results.\n
    """
    logger.info("Entered post processing POST request")
    response_dict = response.dict()
    responses.append(response_dict)
    await websocket_client();
    return AIQueryResponse(**response_dict)

async def websocket_client():
    """
    Processes query response from websocket server in verification server \n
    Returns:  \n
        Realtime validated query.\n
    """
    uri = "ws://api-verification:8002/ws"  # Use the service name in Docker
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello from Post processing server!")
        response = await websocket.recv()
        print(f"Response from Verification {response}")
        return response

if __name__ == "__main__":
    asyncio.run(websocket_client())
