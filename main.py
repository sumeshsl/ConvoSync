from fastapi import FastAPI
from app.routes import queryRoutes

# Initialize the FastAPI app
app = FastAPI(title="ConvoSync API", version="1.0.0")

# Include the example routes
app.include_router(queryRoutes.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to ConvoSync API!"}
