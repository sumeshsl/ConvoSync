from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import postprocessing_routes, threading,uvicorn

# Initialize the FastAPI app
app = FastAPI(title="AdaptAI PostProcessing", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],#TODO: Edit it to match the webapi
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include the routes
app.include_router(postprocessing_routes.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to Postprocessing API!"}


# Start Redis Polling in a Separate Thread
# polling_thread = threading.Thread(target=redis_polling, daemon=True)
# polling_thread.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)