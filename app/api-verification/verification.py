from fastapi import FastAPI, WebSocket
from typing import List
import verification_routes

# Initialize the FastAPI app
app = FastAPI(title="AdaptAI Verification", version="1.0.0")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

# Include the example routes
app.include_router(verification_routes.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to Verification API!"}


connected_clients: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message: {data}")
            for client in connected_clients:
                await client.send_text(f"Echo: {data}")
    except:
        connected_clients.remove(websocket)
        await websocket.close()
