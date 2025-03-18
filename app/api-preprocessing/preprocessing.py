from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import preprocessing_routes

# Initialize the FastAPI app
app = FastAPI(title="AdaptAI API", version="1.0.0")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],#TODO: Edit it to match the webapi
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include the example routes
app.include_router(preprocessing_routes.router)